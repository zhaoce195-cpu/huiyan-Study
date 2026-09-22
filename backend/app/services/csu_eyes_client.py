"""
CSU-EYES 诊断 API 客户端
=======================
对接 CSU-EYES 眼科 AI 平台。
公网 API：http://113.219.243.122:9050/api/v1（注意：9080 是门户页面，不接收 POST）

- POST /api/v1/inference/ma-detection      (FormData: image, model_id?)
- POST /api/v1/inference/dr-grading        (FormData: left_eye, right_eye, model_id?)
- POST /api/v1/inference/comprehensive     (FormData: left_eye, right_eye, tasks?)

特性：
- 使用 requests（项目已装），通过 starlette.run_in_threadpool 异步化
- timeout / 失败重试 1 次（不针对 4xx 重试）
- 自动按扩展名计算正确的 multipart Content-Type，避免上游因 octet-stream 拒绝
- 405 / 415 / 422 等 4xx 错误统一转 502 Bad Gateway 抛出，并保留上游错误描述
- 返回原始 JSON dict；调用方负责解析

不在本模块做：
- 数据库写入（交给 diagnosis_service）
- base64 落盘（交给 utils.save_b64_image_to_screening）
"""

from __future__ import annotations

import contextvars
import io
import logging
import mimetypes
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlsplit, urlunsplit

import requests
from fastapi import HTTPException, status
from PIL import Image, ImageOps
from starlette.concurrency import run_in_threadpool

from app.core.config import settings


logger = logging.getLogger(__name__)


# ============================================================
#                    工具
# ============================================================

# 默认请求头：明确告知服务端期望 JSON 响应
_DEFAULT_HEADERS: Dict[str, str] = {
    "Accept": "application/json",
    "User-Agent": "huiyan-cloud/1.0 (csu-eyes-client)",
}

# CSU-EYES 实测仅接受 JPEG / PNG（webp/bmp/tiff 会返回 400 Invalid file type）
_UPSTREAM_ACCEPTED_EXT = {".jpg", ".jpeg", ".png"}

# 受支持的图片 MIME（用于 multipart 文件 content-type）
_IMAGE_MIME_FALLBACK = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
}


def _api(path: str) -> str:
    base = (settings.CSU_EYES_BASE_URL or "").rstrip("/")
    if not base:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="未配置 CSU-EYES 基础 URL",
        )
    return f"{base}/api/v1{path}"


def _file_tuple(p: Path) -> Tuple[str, bytes, str]:
    """
    生成 requests files 三元组：(name, bytes, content_type)

    CSU-EYES 上游仅接受 JPEG / PNG。本地保存层会把所有上传图重编码成 WEBP，
    若直接转发会触发 `400: Invalid file type`。这里做一次按需转码：
    - 已是 .jpg / .jpeg / .png：原样上传
    - 其它格式（.webp / .bmp / .tif 等）：用 Pillow 解码后重编码为 JPEG，
      上传文件名也强制改 `.jpg`，content-type 用 `image/jpeg`。
    """
    suffix = p.suffix.lower()

    if suffix in _UPSTREAM_ACCEPTED_EXT:
        mime, _ = mimetypes.guess_type(p.name)
        ctype = mime or _IMAGE_MIME_FALLBACK.get(suffix, "image/jpeg")
        return (p.name, p.read_bytes(), ctype)

    # 需要转码 → JPEG
    try:
        with Image.open(p) as img:
            img = ImageOps.exif_transpose(img)
            if img.mode not in ("RGB",):
                img = img.convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=92, optimize=True)
            jpeg_bytes = buf.getvalue()
    except Exception as e:
        logger.warning("[csu-eyes] 转码失败 %s: %s", p.name, e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "文件格式不支持，请上传 JPG/PNG 格式的眼底图。"
                f"（解析失败：{p.name}）"
            ),
        )

    upload_name = f"{p.stem}.jpg"
    return (upload_name, jpeg_bytes, "image/jpeg")


def _extract_upstream_message(resp: requests.Response) -> str:
    """从上游响应里尽量挖出可读错误信息"""
    try:
        js = resp.json()
        if isinstance(js, dict):
            for k in ("detail", "error", "message", "msg"):
                v = js.get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip()
            return str(js)[:300]
    except Exception:
        pass
    text = (resp.text or "").strip()
    return text[:300] or "(空响应)"


def _classify_4xx(status_code: int, message: str, url: str) -> HTTPException:
    """
    把 4xx 转换为对调用方友好的 502，附带可定位问题的明确提示。
    405 通常意味着 base url 端口配错（CSU-EYES API 仅在 9050）。
    """
    hint = ""
    if status_code == 400 and "invalid file type" in message.lower():
        hint = (
            "上游拒收文件类型 — 请上传 JPG/PNG 格式的眼底图。"
            "WebP/BMP/TIFF 已自动转码为 JPEG，若仍报此错误说明文件本身损坏或非真实图片。"
        )
    elif status_code == 405:
        hint = (
            "请求方法不被接受 — 通常说明 CSU_EYES_BASE_URL 指向了静态站点端口（9080）。"
            "请改为 9050（公网 API）或 5000（局域网）。"
        )
    elif status_code == 415:
        hint = "上游不接受当前 Content-Type，已降级到具体 image/* MIME，仍失败请检查文件本身。"
    elif status_code == 422:
        hint = "上游校验失败，常见原因：表单字段名不匹配 / 缺少必填项。"
    elif status_code == 404:
        hint = (
            "上游路径不存在；请确认 base url 是否包含 /api/v1，以及接口路径是否正确。"
        )
    detail = f"CSU-EYES {status_code}：{message}"
    if hint:
        detail = f"{detail} | 提示：{hint}"
    detail = f"{detail} | URL={url}"
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=detail,
    )


# 连通性预检的超时。推理本身慢是正常的，但「连得上却永不回数据」
# 应当立刻判定，而不是让用户干等。
# 连接超时单独收短：配错的内网地址（如 192.168.2.103:5000）不应每次都占满 4 秒。
PREFLIGHT_CONNECT_TIMEOUT = 1.5
PREFLIGHT_TIMEOUT = 4.0

# 配置里的内网地址（如 192.168.2.103:5000）不在同一网段时会超时。
# 公网 9050 是同一套 CSU-EYES 接口，预检失败时改走这里，避免质量评估整批失败。
PUBLIC_CSU_EYES_BASE = "http://113.219.243.122:9050"

# 刚成功过的地址，短时间内 HEAD 偶发超时不再把整次判读打成 503。
# 上一张图能判、下一张图却报「通道断开」，就是预检在正式上传前被一次超时否决。
_GOOD_BASE_TTL = 600.0
_UNREACHABLE_COOLDOWN = 60.0
_route_lock = threading.Lock()
_last_good_base = ""
_last_good_at = 0.0
_unreachable_until: Dict[str, float] = {}

# 本次调用实际选中的算法地址。只在 preflight() 里写入。
_selected_base: contextvars.ContextVar[str] = contextvars.ContextVar(
    "csu_eyes_selected_base", default="",
)


def _candidate_bases() -> List[str]:
    primary = (settings.CSU_EYES_BASE_URL or "").rstrip("/")
    bases: List[str] = []
    if primary:
        bases.append(primary)
    if PUBLIC_CSU_EYES_BASE not in bases:
        bases.append(PUBLIC_CSU_EYES_BASE)
    return bases


def _remember_good_base(base: str) -> None:
    global _last_good_base, _last_good_at
    base = (base or "").rstrip("/")
    if not base:
        return
    with _route_lock:
        _last_good_base = base
        _last_good_at = time.monotonic()
        _unreachable_until.pop(base, None)


def _recent_good_base() -> str:
    with _route_lock:
        if _last_good_base and (time.monotonic() - _last_good_at) < _GOOD_BASE_TTL:
            return _last_good_base
    return ""


def _mark_unreachable(base: str) -> None:
    with _route_lock:
        _unreachable_until[base] = time.monotonic() + _UNREACHABLE_COOLDOWN


def _is_cooling_down(base: str) -> bool:
    with _route_lock:
        return _unreachable_until.get(base, 0.0) > time.monotonic()


def _reset_route_memory() -> None:
    """单测隔离用，清掉进程内记住的可用地址。"""
    global _last_good_base, _last_good_at
    with _route_lock:
        _last_good_base = ""
        _last_good_at = 0.0
        _unreachable_until.clear()


def _probe_once(base: str) -> Optional[str]:
    """
    探真正会用到的 API 前缀，不要探根路径。

    实测过一次教训：探 `GET /` 时上游有响应，判定「可用」放行，
    而正式的 `POST /api/v1/...` 依旧挂到超时。
    返回 None 表示这个地址可以发正式请求；
    "down" 表示连不上，"timeout" 表示连上了却不回数据。
    """
    try:
        requests.head(
            f"{base}/api/v1",
            timeout=(PREFLIGHT_CONNECT_TIMEOUT, PREFLIGHT_TIMEOUT),
            allow_redirects=False,
        )
        return None
    except requests.exceptions.ConnectTimeout:
        return "down"
    except requests.exceptions.ConnectionError:
        return "down"
    except requests.exceptions.Timeout:
        return "timeout"
    except Exception:
        # 其它异常（如该路径本就返回 404/405）不代表不可用
        return None


def _probe_base(base: str) -> Optional[str]:
    # 公网隧道偶发一次 HEAD 超时，紧接着的下一张图不应直接失败。
    attempts = 2 if base.rstrip("/") == PUBLIC_CSU_EYES_BASE else 1
    last: Optional[str] = "down"
    for _ in range(attempts):
        last = _probe_once(base)
        if last is None or last == "down":
            return last
    return last


def _rewrite_base(url: str, base: str) -> str:
    src = urlsplit(url)
    dst = urlsplit(base)
    if not dst.scheme or not dst.netloc:
        return url
    return urlunsplit((dst.scheme, dst.netloc, src.path, src.query, src.fragment))


def preflight() -> Optional[str]:
    """
    上游是否可用。返回 None 表示可用，否则返回给用户看的原因。

    为什么需要这一步：推理服务经 SSH 反向隧道映射到本机端口，隧道断掉后
    端口仍在监听（sshd 照常 accept），TCP 连得上、HTTP 永远不回数据。
    此时不做预检，请求会一路耗到超时，用户不知道是在算还是已经坏了。

    配置的内网地址超时或拒绝连接时，再试公网 9050。两个都不通才判定失败。
    """
    bases = _candidate_bases()
    if not bases:
        return "未配置算法服务地址"
    recent = _recent_good_base()
    if recent:
        bases = [recent] + [b for b in bases if b != recent]
    primary = (settings.CSU_EYES_BASE_URL or "").rstrip("/") or bases[0]
    last = "算法服务未启动或网络不通"
    saw_timeout = False
    for base in bases:
        if _is_cooling_down(base) and base != recent:
            continue
        reason = _probe_base(base)
        if reason is None:
            _selected_base.set(base)
            if base != primary:
                logger.warning(
                    "[csu-eyes] %s 不可用，改用 %s", primary, base,
                )
            return None
        if reason == "down":
            _mark_unreachable(base)
            last = "算法服务未启动或网络不通"
        else:
            saw_timeout = True
            last = "算法服务无响应（推理通道可能已断开），请联系管理员"
    if saw_timeout and recent:
        logger.warning(
            "[csu-eyes] 预检超时，沿用刚刚成功的地址 %s", recent,
        )
        _selected_base.set(recent)
        return None
    _selected_base.set("")
    return last


def _post_form_sync(
    url: str,
    *,
    files: Dict[str, Tuple[str, bytes, str]],
    data: Optional[Dict[str, str]] = None,
    timeout: float = 90.0,
) -> dict:
    _selected_base.set("")
    reason = preflight()
    if reason:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=reason,
        )
    chosen = _selected_base.get()
    if chosen:
        url = _rewrite_base(url, chosen)

    last_err: Optional[Exception] = None
    # 仅 5xx / 网络错误重试一次；4xx 直接抛出。
    # 注意超时不重试：既然已经等满一个超时周期，再等一遍只是把
    # 用户的等待时间翻倍，结果不会变。
    for attempt in range(2):
        try:
            resp = requests.post(
                url,
                files=files,
                data=data or {},
                headers=_DEFAULT_HEADERS,
                timeout=timeout,
            )
            if 200 <= resp.status_code < 300:
                try:
                    if chosen:
                        _remember_good_base(chosen)
                    return resp.json()
                except ValueError:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"CSU-EYES 返回非 JSON：{(resp.text or '')[:200]}",
                    )
            if 400 <= resp.status_code < 500:
                msg = _extract_upstream_message(resp)
                logger.warning(
                    "[csu-eyes] %s -> %s %s", url, resp.status_code, msg,
                )
                raise _classify_4xx(resp.status_code, msg, url)
            # 5xx：作为可重试错误
            last_err = RuntimeError(
                f"CSU-EYES {resp.status_code}: "
                f"{_extract_upstream_message(resp)}"
            )
            logger.warning("[csu-eyes] 5xx attempt %d: %s", attempt + 1, last_err)
            continue
        except HTTPException:
            raise
        except requests.exceptions.Timeout as e:
            # 超时不重试：已经等满一个超时周期，再来一遍只是把用户的
            # 等待时间翻倍，而结果不会变。此前正是这一条让用户在界面上
            # 干等了近三分钟（90 秒 × 2）。
            logger.warning("[csu-eyes] timeout, not retrying: %s", e)
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"算法服务响应超时（已等待 {timeout:.0f} 秒），请稍后重试",
            )
        except requests.RequestException as e:
            last_err = e
            logger.warning("[csu-eyes] network attempt %d: %s", attempt + 1, e)
            continue
        except Exception as e:
            last_err = e
            continue
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"CSU-EYES 调用失败：{last_err} | URL={url}",
    )


async def _post_form(
    url: str,
    *,
    files: Dict[str, Tuple[str, bytes, str]],
    data: Optional[Dict[str, str]] = None,
    timeout: Optional[float] = None,
) -> dict:
    timeout_sec = float(timeout or settings.CSU_EYES_TIMEOUT_SEC)
    return await run_in_threadpool(
        _post_form_sync, url, files=files, data=data, timeout=timeout_sec,
    )


# ============================================================
#                    具体接口
# ============================================================

async def detect_ma(
    *,
    image_path: Path,
    model_id: Optional[int] = None,
) -> dict:
    """
    微动脉瘤 (MA) 检测。
    返回示例：{
      "record_id": 1,
      "ma_count": 5,
      "overlay_base64": "...",
      "heatmap_base64": "...",
      "inference_time": 0.78
    }
    """
    if not image_path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"待诊断影像不存在：{image_path.name}",
        )
    files = {"image": _file_tuple(image_path)}
    data: Dict[str, str] = {}
    if model_id is not None:
        data["model_id"] = str(model_id)
    return await _post_form(_api("/inference/ma-detection"), files=files, data=data)


async def grade_dr(
    *,
    left_eye_path: Path,
    right_eye_path: Path,
    model_id: Optional[int] = None,
) -> dict:
    """DR 双眼分级。"""
    for p, name in ((left_eye_path, "left_eye"), (right_eye_path, "right_eye")):
        if not p.exists():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{name} 影像不存在：{p.name}",
            )
    files = {
        "left_eye": _file_tuple(left_eye_path),
        "right_eye": _file_tuple(right_eye_path),
    }
    data: Dict[str, str] = {}
    if model_id is not None:
        data["model_id"] = str(model_id)
    return await _post_form(_api("/inference/dr-grading"), files=files, data=data)


async def detect_glaucoma(
    *,
    image_path: Path,
    model_id: Optional[int] = None,
) -> dict:
    """
    青光眼筛查（单图分类）。
    返回示例：{
      "record_id": 76,
      "model": {"name": "青光眼筛查", "task_type": "glaucoma_screening", ...},
      "result": {"prediction": 1, "prediction_name": "青光眼疑似",
                 "prediction_en": "glaucoma_suspect",
                 "probabilities": {"normal": 0.x, "glaucoma": 0.y}}
    }
    """
    if not image_path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"待诊断影像不存在：{image_path.name}",
        )
    files = {"image": _file_tuple(image_path)}
    data: Dict[str, str] = {}
    if model_id is not None:
        data["model_id"] = str(model_id)
    return await _post_form(_api("/inference/glaucoma-screening"), files=files, data=data)


async def assess_image_quality(
    *,
    image_path: Path,
    model_id: Optional[int] = None,
) -> dict:
    """
    眼底图像质量评估（单图三分类：好 / 可用 / 差）。

    用于报告要求的「先质量后诊断」门控：任何练习或临床结论前，
    都应先确认影像可判读。

    返回示例：{
      "record_id": 91,
      "model": {"name": "Image_quality", "task_type": "image_quality", ...},
      "result": {"prediction": 0, "prediction_name": "好",
                 "prediction_en": "good",
                 "probabilities": {"good": 0.x, "usable": 0.y, "poor": 0.z}}
    }
    """
    if not image_path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"待评估影像不存在：{image_path.name}",
        )
    files = {"image": _file_tuple(image_path)}
    data: Dict[str, str] = {}
    if model_id is not None:
        data["model_id"] = str(model_id)
    return await _post_form(_api("/inference/image-quality"), files=files, data=data)


async def comprehensive(
    *,
    image_path: Path,
    tasks: Optional[List[str]] = None,
) -> dict:
    """
    综合诊断（同一张图执行多任务）。
    注意：CSU-EYES 综合诊断官方文档要求双眼参数（left_eye + right_eye），
    但本平台沿用「单图」入口 → 这里把同一张图同时当作 left_eye / right_eye 上传，
    既兼容老调用，也满足上游的字段要求。
    """
    if not image_path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"待诊断影像不存在：{image_path.name}",
        )
    file_tuple = _file_tuple(image_path)
    files = {
        "image": file_tuple,
        "left_eye": file_tuple,
        "right_eye": file_tuple,
    }
    data: Dict[str, str] = {}
    if tasks:
        data["tasks"] = ",".join(tasks)
    return await _post_form(_api("/inference/comprehensive"), files=files, data=data)


__all__ = ["detect_ma", "grade_dr", "detect_glaucoma", "comprehensive"]
