"""
通用工具 — 文件保存、头像处理
"""

import io
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from fastapi import HTTPException, UploadFile, status
from PIL import Image, ImageOps

from app.core.config import settings

# ---------- 路径工具 ----------

def project_root() -> Path:
    """项目根目录（backend/ 这一级）"""
    return Path(__file__).resolve().parent.parent.parent


def avatars_dir() -> Path:
    """绝对路径：头像存储目录"""
    p = project_root() / settings.UPLOAD_DIR / settings.AVATAR_SUBDIR
    p.mkdir(parents=True, exist_ok=True)
    return p


def avatar_url(file_name: str) -> str:
    """根据文件名生成对外访问 URL"""
    return f"{settings.STATIC_URL}/{settings.AVATAR_SUBDIR}/{file_name}"


# ---------- 头像处理 ----------

async def save_avatar(file: UploadFile, user_id: int) -> Tuple[str, str, int]:
    """
    保存用户上传头像，自动压缩为 256x256，返回 (相对URL, 文件名, 字节数)

    校验：
    - 扩展名白名单
    - 文件大小上限
    - 真实读取并通过 Pillow 解码，避免恶意伪装
    """

    # 1. 扩展名校验
    suffix = Path(file.filename or "").suffix.lower()
    if not suffix:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件名缺少扩展名",
        )
    if suffix not in settings.AVATAR_ALLOWED_EXT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的图片格式，允许：{','.join(settings.AVATAR_ALLOWED_EXT)}",
        )

    # 2. 大小校验
    raw = await file.read()
    size_bytes = len(raw)
    if size_bytes <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="上传文件为空",
        )
    if size_bytes > settings.AVATAR_MAX_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"头像最大允许 {settings.AVATAR_MAX_SIZE_MB}MB",
        )

    # 3. 解码 + 压缩为 256x256（保持比例 + 居中裁剪）
    try:
        img = Image.open(io.BytesIO(raw))
        img = ImageOps.exif_transpose(img)              # 修正方向
        img = ImageOps.fit(img, (256, 256), Image.LANCZOS, centering=(0.5, 0.5))
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="图片解析失败，可能为伪装文件",
        )

    # 4. 保存（统一为 webp，体积小）
    save_name = f"u{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}.webp"
    save_path = avatars_dir() / save_name
    img.save(save_path, format="WEBP", quality=85, method=6)

    return avatar_url(save_name), save_name, save_path.stat().st_size


def delete_avatar_file(url_or_name: str) -> None:
    """根据存储的 url / 文件名删除旧头像；安全：不会越权删除其它目录"""
    if not url_or_name:
        return
    file_name = os.path.basename(url_or_name)
    if not file_name:
        return
    target = avatars_dir() / file_name
    try:
        if target.exists() and target.is_file():
            target.unlink()
    except Exception:
        # 删除失败不影响主流程
        pass


# ============================================================
#   眼底图（AI 筛查）保存工具
# ============================================================

def screening_dir() -> Path:
    """绝对路径：眼底图存储目录"""
    p = project_root() / settings.UPLOAD_DIR / settings.SCREENING_SUBDIR
    p.mkdir(parents=True, exist_ok=True)
    return p


def screening_url(file_name: str) -> str:
    """根据文件名生成对外访问 URL"""
    return f"{settings.STATIC_URL}/{settings.SCREENING_SUBDIR}/{file_name}"


async def save_fundus_image(file: UploadFile, user_id: int) -> Tuple[str, str, int]:
    """
    保存上传的眼底图，返回 (相对URL, 文件名, 字节数)

    校验：
    - 扩展名白名单
    - 大小上限（默认 20MB）
    - 通过 Pillow 解码确认是图片
    - 自动重新编码为 webp（防伪装、压缩体积）

    返回的文件名可作为业务编号的一部分写入 ScreeningCase.image_paths
    """

    # 1. 扩展名校验
    suffix = Path(file.filename or "").suffix.lower()
    if not suffix:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件名缺少扩展名",
        )
    if suffix not in settings.SCREENING_ALLOWED_EXT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的图片格式，允许：{','.join(settings.SCREENING_ALLOWED_EXT)}",
        )

    # 2. 大小校验
    raw = await file.read()
    size_bytes = len(raw)
    if size_bytes <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="上传文件为空",
        )
    if size_bytes > settings.SCREENING_MAX_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"眼底图最大允许 {settings.SCREENING_MAX_SIZE_MB}MB",
        )

    # 3. 解码 + 重新编码
    try:
        img = Image.open(io.BytesIO(raw))
        img = ImageOps.exif_transpose(img)
        # 保留原图分辨率（眼底图分辨率重要，不裁剪）；过大才等比缩放
        max_side = 2048
        if max(img.size) > max_side:
            ratio = max_side / max(img.size)
            new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
            img = img.resize(new_size, Image.LANCZOS)
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="图片解析失败，可能为伪装文件",
        )

    # 4. 保存（统一为 webp）
    save_name = (
        f"f{user_id}_"
        f"{datetime.now().strftime('%Y%m%d%H%M%S')}_"
        f"{uuid.uuid4().hex[:8]}.webp"
    )
    save_path = screening_dir() / save_name
    img.save(save_path, format="WEBP", quality=90, method=6)

    return screening_url(save_name), save_name, save_path.stat().st_size


def delete_fundus_file(url_or_name: str) -> None:
    """删除眼底图文件，限定在筛查目录内，防越权"""
    if not url_or_name:
        return
    file_name = os.path.basename(url_or_name)
    if not file_name:
        return
    target = screening_dir() / file_name
    try:
        if target.exists() and target.is_file():
            target.unlink()
    except Exception:
        pass


def resolve_screening_file(url_or_name: str) -> Optional[Path]:
    """
    把眼底图相对 URL（/static/screening/xxx.webp）映射到磁盘绝对路径。
    路径越权防护：限定在 screening_dir() 内。
    找不到返回 None。
    """
    if not url_or_name:
        return None
    file_name = os.path.basename(url_or_name)
    if not file_name:
        return None
    base = screening_dir().resolve()
    target = (base / file_name).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        return None
    if target.exists() and target.is_file():
        return target
    return None


def save_heatmap_from_data_url(data_url: str, case_no: str, eye: str) -> str:
    """
    把 DRGCNN 返回的 data:image/jpeg;base64,... 落盘到 screening 目录。
    返回对外访问 URL（可直接写入 ScreeningResult.heatmap_path）。
    解析失败返回空字符串（调用方自行容错）。
    """
    if not data_url or ";base64," not in data_url:
        return ""
    try:
        header, b64_data = data_url.split(",", 1)
        # 默认 jpeg；只把 png/webp 单独识别一下
        ext = ".jpg"
        if "image/png" in header:
            ext = ".png"
        elif "image/webp" in header:
            ext = ".webp"
        import base64 as _b64
        raw = _b64.b64decode(b64_data)
        if not raw:
            return ""
        save_name = (
            f"heat_{case_no}_{(eye or 'OU').lower()}_"
            f"{datetime.now().strftime('%Y%m%d%H%M%S')}{ext}"
        )
        save_path = screening_dir() / save_name
        save_path.write_bytes(raw)
        return screening_url(save_name)
    except Exception:
        return ""


def save_b64_image_to_screening(
    b64: str,
    *,
    prefix: str = "diag",
    case_no: str = "",
    suffix: str = "",
    ext: str = "png",
) -> str:
    """
    把不带 data:image/...;base64, 前缀的纯 base64 图片落盘到 screening 目录。
    返回对外 URL；失败返回空字符串。
    """
    if not b64:
        return ""
    try:
        # 兼容带前缀的输入
        if ";base64," in b64:
            b64 = b64.split(",", 1)[1]
        import base64 as _b64
        raw = _b64.b64decode(b64)
        if not raw:
            return ""
        parts = [prefix]
        if case_no:
            parts.append(case_no)
        if suffix:
            parts.append(suffix)
        parts.append(datetime.now().strftime("%Y%m%d%H%M%S"))
        parts.append(uuid.uuid4().hex[:6])
        save_name = "_".join(parts) + f".{ext.lower()}"
        save_path = screening_dir() / save_name
        save_path.write_bytes(raw)
        return screening_url(save_name)
    except Exception:
        return ""


# ============================================================
#   体检报告 PDF 落盘工具
# ============================================================

REPORT_SUBDIR = "reports"


def report_pdf_dir(year_month: str = "") -> Path:
    """
    报告 PDF 存储目录：app/static/reports/<YYYYMM>/
    - year_month 为空时使用当前年月
    """
    ym = year_month or datetime.now().strftime("%Y%m")
    p = project_root() / settings.UPLOAD_DIR / REPORT_SUBDIR / ym
    p.mkdir(parents=True, exist_ok=True)
    return p


def report_pdf_url(year_month: str, file_name: str) -> str:
    return f"{settings.STATIC_URL}/{REPORT_SUBDIR}/{year_month}/{file_name}"


def save_report_pdf(case_no: str, pdf_bytes: bytes) -> Tuple[str, Path]:
    """
    把生成好的 PDF 字节流落盘，返回 (相对URL, 绝对路径)。
    文件名固定为 {case_no}_{YYYYMMDD_HHMMSS}.pdf。
    """
    safe_no = "".join(c for c in (case_no or "case") if c.isalnum() or c in ("-", "_")) or "case"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"{safe_no}_{ts}.pdf"
    ym = datetime.now().strftime("%Y%m")
    target_dir = report_pdf_dir(ym)
    target = target_dir / file_name
    target.write_bytes(pdf_bytes)
    return report_pdf_url(ym, file_name), target


def resolve_report_pdf(rel_url_or_path: str) -> Optional[Path]:
    """
    把 save_report_pdf 返回的相对 URL（或保存到 DB 的 path）
    解析为绝对磁盘路径，用于安全读取。
    - 仅返回位于 reports/ 目录下的文件，跨目录访问视为非法。
    """
    if not rel_url_or_path:
        return None
    base_dir = (project_root() / settings.UPLOAD_DIR / REPORT_SUBDIR).resolve()
    # 兼容三种格式：
    #   1) /static/reports/202605/xxx.pdf
    #   2) reports/202605/xxx.pdf
    #   3) 绝对路径（仅当位于 reports 目录下才允许）
    raw = rel_url_or_path.strip().replace("\\", "/")
    candidates: list[Path] = []

    if raw.startswith(settings.STATIC_URL.rstrip("/") + "/"):
        rel = raw[len(settings.STATIC_URL.rstrip("/") + "/"):]
        candidates.append(project_root() / settings.UPLOAD_DIR / rel)
    elif raw.startswith("/"):
        # 绝对路径
        candidates.append(Path(raw))
    else:
        # 相对项目根 / static
        candidates.append(project_root() / settings.UPLOAD_DIR / raw)
        candidates.append(project_root() / raw)

    for c in candidates:
        try:
            full = c.resolve()
        except Exception:
            continue
        try:
            full.relative_to(base_dir)
        except ValueError:
            continue
        if full.exists() and full.is_file():
            return full
    return None


# ============================================================
#   通用文件上传（公共模块 / common/upload）
# ============================================================

# 通用上传白名单（按 mime/扩展名双重校验）
COMMON_ALLOWED_EXT = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp",     # 图片
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".csv",  # 文档
    ".zip", ".rar", ".7z",                                # 压缩
    ".mp4", ".mp3", ".wav",                               # 音视频
}
COMMON_MAX_SIZE_MB = 50

# 不允许的危险扩展名（即便 magic 检测通过也拒绝，作为兜底）
_DANGEROUS_EXT = {
    ".exe", ".dll", ".bat", ".cmd", ".sh", ".ps1", ".js",
    ".vbs", ".scr", ".jar", ".com", ".msi",
}

_MIME_BY_EXT = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".png": "image/png", ".gif": "image/gif",
    ".bmp": "image/bmp", ".webp": "image/webp",
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".txt": "text/plain", ".csv": "text/csv",
    ".zip": "application/zip",
    ".rar": "application/vnd.rar",
    ".7z": "application/x-7z-compressed",
    ".mp4": "video/mp4",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
}


def common_upload_dir(biz: str) -> Path:
    """业务子目录：app/static/uploads/<biz>/<YYYYMMDD>/"""
    biz_safe = "".join(c for c in (biz or "misc") if c.isalnum() or c in ("-", "_")).lower() or "misc"
    p = (
        project_root()
        / settings.UPLOAD_DIR
        / "uploads"
        / biz_safe
        / datetime.now().strftime("%Y%m%d")
    )
    p.mkdir(parents=True, exist_ok=True)
    return p


def common_upload_url(biz: str, ymd: str, file_name: str) -> str:
    biz_safe = "".join(c for c in (biz or "misc") if c.isalnum() or c in ("-", "_")).lower() or "misc"
    return f"{settings.STATIC_URL}/uploads/{biz_safe}/{ymd}/{file_name}"


async def save_common_upload(
    file: UploadFile,
    biz: str,
    user_id: int,
) -> Tuple[str, str, int, str]:
    """
    通用上传：返回 (相对URL, 文件名, 字节数, mime)

    安全策略：
    - 扩展名白名单 + 危险扩展名黑名单
    - 大小上限 50MB
    - 文件名仅用 user_id + 时间戳 + 随机串 + 安全后缀，丢弃用户原始文件名
    - 图片类额外通过 Pillow 解码确认（其它类型只做扩展名/大小校验）
    """
    suffix = Path(file.filename or "").suffix.lower()
    if not suffix:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件名缺少扩展名",
        )
    if suffix in _DANGEROUS_EXT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不允许上传可执行/脚本类文件",
        )
    if suffix not in COMMON_ALLOWED_EXT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件类型：{suffix}",
        )

    raw = await file.read()
    size_bytes = len(raw)
    if size_bytes <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="上传文件为空",
        )
    if size_bytes > COMMON_MAX_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"文件最大允许 {COMMON_MAX_SIZE_MB}MB",
        )

    # 图片类做严格解码
    if suffix in {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}:
        try:
            with Image.open(io.BytesIO(raw)) as im:
                im.verify()  # 仅检查不解码全部像素
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="图片解析失败，可能为伪装文件",
            )

    save_name = (
        f"u{user_id}_"
        f"{datetime.now().strftime('%Y%m%d%H%M%S')}_"
        f"{uuid.uuid4().hex[:8]}{suffix}"
    )
    target_dir = common_upload_dir(biz)
    save_path = target_dir / save_name
    save_path.write_bytes(raw)

    ymd = datetime.now().strftime("%Y%m%d")
    rel_url = common_upload_url(biz, ymd, save_name)
    mime = _MIME_BY_EXT.get(suffix, file.content_type or "application/octet-stream")
    return rel_url, save_name, size_bytes, mime
