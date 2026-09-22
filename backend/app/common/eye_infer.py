"""
从眼底图判断眼别。

OD 右眼：视盘亮斑在画面右侧（质心 x / 宽 ≥ 0.60）
OS 左眼：视盘亮斑在画面左侧（≤ 0.40）
OU 双眼：画面里有两块分开的眼底
UK：对不准，或亮斑靠近中间。中间区域不猜。

医生或学员已经选了 OD / OS / OU 时，不再改写。
文件名里的裸 OD / OS 不参与判断（IDRiD 的 *_OD.png 是视盘 mask，不是右眼）。
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageOps

from app.common.utils import project_root
from app.core.config import settings

EXPLICIT_EYES = ("OD", "OS", "OU")


def resolve_static_file(url: str) -> Optional[Path]:
    """把 /static/... 相对地址解析到 app/static 内的文件，越权或不存在则返回 None。"""
    if not url or not isinstance(url, str):
        return None
    raw = url.strip().split("?", 1)[0]
    prefix = settings.STATIC_URL.rstrip("/") + "/"
    if raw.startswith(prefix):
        rel = raw[len(prefix):]
    elif not raw.startswith("/"):
        rel = raw
    else:
        return None
    base = (project_root() / settings.UPLOAD_DIR).resolve()
    candidate = (base / rel).resolve()
    if base not in candidate.parents and candidate != base:
        return None
    return candidate if candidate.is_file() else None


def filename_eye_hint(name: str) -> Optional[str]:
    """只认「左眼 / 右眼 / 双眼」和 left/right/both eye。不认文件名里单独的 OD、OS。"""
    raw = name or ""
    text = raw.lower()
    if "双眼" in raw or "both eyes" in text or "binocular" in text:
        return "OU"
    if "右眼" in raw or "right eye" in text:
        return "OD"
    if "左眼" in raw or "left eye" in text:
        return "OS"
    return None


def infer_eye_laterality(path: Path) -> str:
    """对一张已落盘的眼底图返回 OD / OS / OU / UK。读图失败时返回 UK，不打断上传。"""
    try:
        with Image.open(path) as im:
            im = ImageOps.exif_transpose(im) or im
            im = im.convert("RGB")
            im.thumbnail((180, 180))
            arr = np.asarray(im)
    except Exception:
        return "UK"
    if arr.ndim != 3 or arr.shape[0] < 8 or arr.shape[1] < 8:
        return "UK"
    h, w = arr.shape[:2]
    lum = (
        0.2126 * arr[:, :, 0] + 0.7152 * arr[:, :, 1] + 0.0722 * arr[:, :, 2]
    ).astype(np.float32)
    retina = lum > 18
    if int(retina.sum()) < 60:
        return "UK"
    labels, n = _label_components(retina)
    areas = [int((labels == i).sum()) for i in range(1, n + 1)]
    big = [a for a in areas if a > 0.12 * h * w]
    if len(big) >= 2:
        return "OU"
    vals = lum[retina]
    thr = float(np.percentile(vals, 98.2))
    bright = (lum >= thr) & retina
    bl, bn = _label_components(bright)
    if bn == 0:
        return "UK"
    best_i, best_a = 1, 0
    for i in range(1, bn + 1):
        area = int((bl == i).sum())
        if area > best_a:
            best_i, best_a = i, area
    _ys, xs = np.nonzero(bl == best_i)
    if xs.size == 0:
        return "UK"
    cx = float(xs.mean()) / float(w)
    if cx >= 0.60:
        return "OD"
    if cx <= 0.40:
        return "OS"
    return "UK"


def resolve_uploaded_eye(
    eye: str,
    *,
    file_name: str = "",
    image_path: Optional[Path] = None,
    role: str = "original",
    inherited: str = "",
) -> str:
    """
    上传眼别。

    已选 OD / OS / OU 原样保留。
    未选（UK 或空）且是原图时，按视盘位置判断；判断不出再用文件名里的左眼/右眼/双眼。
    标注层、mask 不跑视盘检测，跟该病例唯一明确的原图眼别。
    """
    code = (eye or "").strip().upper()
    if code in EXPLICIT_EYES:
        return code
    hinted = filename_eye_hint(file_name)
    if role == "original":
        pred = "UK"
        if image_path is not None:
            pred = infer_eye_laterality(image_path)
        if pred in EXPLICIT_EYES:
            return pred
        return hinted or "UK"
    if hinted:
        return hinted
    inherited_code = (inherited or "").strip().upper()
    if inherited_code in EXPLICIT_EYES:
        return inherited_code
    return "UK"


def laterality_from_paths(paths) -> str:
    """
    由 image_paths 汇总病例眼别。
    左右都有，或同时有 OU 桶和单眼桶，记为双眼。
    只有 UK、或没有图，记为 UK，不记成双眼。
    只有 OU 桶仍记为双眼（历史数据和明确的双眼图）。
    """
    if not isinstance(paths, dict):
        return "UK"
    has_od = bool(paths.get("OD"))
    has_os = bool(paths.get("OS"))
    has_ou = bool(paths.get("OU"))
    if has_od and has_os:
        return "OU"
    if has_ou and (has_od or has_os):
        return "OU"
    if has_od:
        return "OD"
    if has_os:
        return "OS"
    if has_ou:
        return "OU"
    return "UK"


def _label_components(mask: np.ndarray):
    h, w = mask.shape
    labels = np.zeros((h, w), dtype=np.int32)
    n = 0
    ys, xs = np.nonzero(mask)
    for y0, x0 in zip(ys.tolist(), xs.tolist()):
        if labels[y0, x0]:
            continue
        n += 1
        stack = [(y0, x0)]
        labels[y0, x0] = n
        while stack:
            y, x = stack.pop()
            for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and labels[ny, nx] == 0:
                    labels[ny, nx] = n
                    stack.append((ny, nx))
    return labels, n
