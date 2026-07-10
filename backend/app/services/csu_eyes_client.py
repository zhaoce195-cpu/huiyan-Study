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

import io
import logging
import mimetypes
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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


def _post_form_sync(
    url: str,
    *,
    files: Dict[str, Tuple[str, bytes, str]],
    data: Optional[Dict[str, str]] = None,
    timeout: float = 90.0,
) -> dict:
    last_err: Optional[Exception] = None
    # 仅 5xx / 网络错误重试一次；4xx 直接抛出
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
