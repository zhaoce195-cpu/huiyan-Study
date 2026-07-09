"""
DRGCNN 真实 DR 模型客户端
=========================

封装 http://113.219.243.122:9050/predict_twoeyes：
- 单例 session（连接池 + 重试）
- 输入归一化：HTTP URL / 本地路径 / data:image/...;base64,... / bytes
- 错误码语义化：400/404/500 → DRGCNNError；502/503/504 自动重试
- 结果解析：返回 PredictResult，便于映射到 ScreeningResult

仅供 services/screening_service.py 内部调用。
"""

from __future__ import annotations

import base64
import io
import logging
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.core.config import settings

logger = logging.getLogger(__name__)


GRADE_TEXT: Dict[int, str] = {
    0: "无 DR",
    1: "轻度 NPDR",
    2: "中度 NPDR",
    3: "重度 NPDR",
    4: "增殖性 PDR",
}


class DRGCNNError(RuntimeError):
    """DRGCNN 调用失败 / 响应异常时统一抛出。"""

    def __init__(self, msg: str, status_code: Optional[int] = None) -> None:
        super().__init__(msg)
        self.status_code = status_code


@dataclass
class EyeOutcome:
    grade: int
    grade_text: str
    probability: float
    image_name: str
    heatmap_base64: str  # 完整 data URL，可直接落盘 / 给前端 <img src=>


@dataclass
class PredictResult:
    left: EyeOutcome
    right: EyeOutcome
    raw: Dict[str, Any]

    @property
    def max_grade(self) -> int:
        return max(self.left.grade, self.right.grade)


# ============================================================
# 输入归一化
# ============================================================

def _is_http_url(s: str) -> bool:
    if not s:
        return False
    parsed = urlparse(s)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _is_data_url(s: str) -> bool:
    return isinstance(s, str) and s.startswith("data:") and ";base64," in s


def _bytes_to_data_url(raw: bytes, mime: str = "image/jpeg") -> str:
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


def _shrink_if_too_large(raw: bytes, max_bytes: int) -> Tuple[bytes, str]:
    """超过阈值时用 Pillow 等比缩放并重编为 JPEG，避免请求体爆掉。"""
    if len(raw) <= max_bytes:
        return raw, "image/jpeg"
    try:
        from PIL import Image, ImageOps  # 项目里上传环节已依赖 Pillow
        img = Image.open(io.BytesIO(raw))
        img = ImageOps.exif_transpose(img)
        max_side = 1024
        if max(img.size) > max_side:
            ratio = max_side / max(img.size)
            img = img.resize(
                (int(img.size[0] * ratio), int(img.size[1] * ratio)),
                Image.LANCZOS,
            )
        if img.mode != "RGB":
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=88)
        return buf.getvalue(), "image/jpeg"
    except Exception as e:
        logger.warning("DRGCNN 图像压缩失败，按原样上送：%s", e)
        return raw, "image/jpeg"


def _path_to_data_url(path: Path, max_bytes: int) -> str:
    if not path.exists() or not path.is_file():
        raise DRGCNNError(f"本地图像文件不存在: {path}")
    raw = path.read_bytes()
    if not raw:
        raise DRGCNNError(f"图像文件为空: {path}")
    raw, mime_guess = _shrink_if_too_large(raw, max_bytes)
    mime = mimetypes.guess_type(str(path))[0] or mime_guess
    if mime not in ("image/jpeg", "image/png", "image/webp"):
        # 服务端公告 JPEG，PNG 实测可用；其他统一转 JPEG
        raw, mime = _shrink_if_too_large(raw, max_bytes)
    return _bytes_to_data_url(raw, mime)


def _normalize(image: Union[str, Path, bytes], max_bytes: int) -> str:
    """统一为可放进 leftUrl/rightUrl 的字符串。"""
    if isinstance(image, bytes):
        if not image:
            raise DRGCNNError("图像字节为空")
        raw, mime = _shrink_if_too_large(image, max_bytes)
        return _bytes_to_data_url(raw, mime)
    s = str(image).strip()
    if _is_http_url(s) or _is_data_url(s):
        return s
    return _path_to_data_url(Path(s), max_bytes)


# ============================================================
# 客户端单例
# ============================================================

_session: Optional[requests.Session] = None


def _get_session() -> requests.Session:
    global _session
    if _session is not None:
        return _session
    s = requests.Session()
    retry = Retry(
        total=2,
        backoff_factor=0.6,
        status_forcelist=[502, 503, 504],
        allowed_methods=frozenset(["GET", "POST"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_maxsize=8)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    _session = s
    return s


def predict_twoeyes(
    left: Union[str, Path, bytes],
    right: Union[str, Path, bytes],
    *,
    base_url: Optional[str] = None,
    timeout: Optional[int] = None,
) -> PredictResult:
    """同步调用 /predict_twoeyes，返回结构化结果。"""
    base = (base_url or settings.DRGCNN_BASE_URL).rstrip("/")
    timeout_s = timeout or settings.DRGCNN_TIMEOUT_SEC
    max_bytes = settings.DRGCNN_MAX_BYTES

    payload = {
        "leftUrl": _normalize(left, max_bytes),
        "rightUrl": _normalize(right, max_bytes),
    }

    try:
        resp = _get_session().post(
            f"{base}/predict_twoeyes",
            json=payload,
            timeout=timeout_s,
        )
    except requests.RequestException as e:
        raise DRGCNNError(f"请求 DRGCNN 失败：{e}") from e

    if resp.status_code != 200:
        try:
            data = resp.json()
            err = str(data.get("error") or data)
        except Exception:
            err = resp.text[:300]
        raise DRGCNNError(
            f"DRGCNN 返回 {resp.status_code}：{err}",
            status_code=resp.status_code,
        )

    try:
        raw = resp.json()
    except ValueError as e:
        raise DRGCNNError(f"DRGCNN 响应不是合法 JSON：{e}") from e
    if isinstance(raw, dict) and "error" in raw:
        raise DRGCNNError(f"服务端报错：{raw['error']}")

    def _eye(prefix: str) -> EyeOutcome:
        grade = int(raw.get(f"{prefix}_prediction", -1))
        return EyeOutcome(
            grade=grade,
            grade_text=GRADE_TEXT.get(grade, f"未知({grade})"),
            probability=float(raw.get(f"{prefix}_probability", 0.0)),
            image_name=str(raw.get(f"{prefix}_image_name", "")),
            heatmap_base64=str(raw.get(f"{prefix}_heatmap_base64", "")),
        )

    return PredictResult(
        left=_eye("left_eye"),
        right=_eye("right_eye"),
        raw=raw,
    )


__all__ = [
    "DRGCNNError",
    "EyeOutcome",
    "PredictResult",
    "GRADE_TEXT",
    "predict_twoeyes",
]
