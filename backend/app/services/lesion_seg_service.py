"""
教师端多病灶分割。

算法来自 D:\\huiyan\\multi_lesions_seg.zip：VM-UNet，类别为背景、出血(HE)、
硬性渗出(EX)、软性渗出(SE)。推理代码在 backend/vendor/multi_lesions_seg，
权重在 backend/data/multi_lesions/best_mdice.pth（不进仓库）。

这里只生成叠加图，不写阅片记录，不改学员评分，也不代替 CSU-EYES 分级。
启动时不加载 PyTorch；缺依赖时接口如实返回 available=false。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Optional

from fastapi import HTTPException

from app.common.utils import project_root
from app.core.config import settings
from app.db.models.user import RoleEnum, User
from app.services.reading_service import ReadingService
from app.services.training_ai_service import _resolve_static_file

_LABELS = {"HE": "出血", "EX": "硬性渗出", "SE": "软性渗出"}
_loaded_model = None


def _vendor_root() -> Path:
    return project_root() / "vendor" / "multi_lesions_seg"


def _weight_file() -> Optional[Path]:
    candidates = []
    if settings.MULTI_LESION_WEIGHTS:
        candidates.append(Path(settings.MULTI_LESION_WEIGHTS))
    candidates.append(project_root() / "data" / "multi_lesions" / "best_mdice.pth")
    candidates.append(Path(r"D:/huiyan/multi_lesions_seg/weights/best_mdice.pth"))
    for path in candidates:
        try:
            if path.is_file() and path.stat().st_size > 1_000_000:
                return path
        except OSError:
            continue
    return None


def _empty(message: str) -> dict:
    return {
        "available": False,
        "overlayUrl": "",
        "counts": {"HE": 0, "EX": 0, "SE": 0},
        "message": message,
    }


def _allowed_urls(source) -> set[str]:
    allowed = {u for u in (source.images or []) if u}
    groups = source.image_groups or {}
    if isinstance(groups, dict):
        for urls in groups.values():
            for url in urls or []:
                if url:
                    allowed.add(url)
    return allowed


def _infer(image_path: Path, weight: Path, case_id: int) -> dict:
    global _loaded_model
    root = _vendor_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    import torch
    from predict_multilesions import load_model, predict_one_image

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if _loaded_model is None:
        _loaded_model = load_model(weight, device)
    out_dir = project_root() / settings.UPLOAD_DIR / "lesion-seg" / str(case_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    summary = predict_one_image(
        image_path=image_path,
        weight_path=weight,
        output_dir=out_dir,
        device=device,
        model=_loaded_model,
        save_probabilities=False,
    )
    seconds = round(time.perf_counter() - started, 1)
    counts_raw = summary.get("pixel_counts") or {}
    counts = {
        "HE": int(counts_raw.get("HE") or 0),
        "EX": int(counts_raw.get("EX") or 0),
        "SE": int(counts_raw.get("SE") or 0),
    }
    overlay_name = f"{image_path.stem}_overlay.png"
    overlay_path = out_dir / overlay_name
    if not overlay_path.is_file():
        raise RuntimeError("分割跑完了，但没有写出叠加图")
    overlay_url = (
        f"{settings.STATIC_URL.rstrip('/')}/lesion-seg/{case_id}/{overlay_name}"
        f"?t={int(time.time())}"
    )
    parts = [f"{_LABELS[key]} {counts[key]} 像素" for key in ("HE", "EX", "SE")]
    return {
        "available": True,
        "overlayUrl": overlay_url,
        "counts": counts,
        "device": str(device),
        "seconds": seconds,
        "message": "已叠加：" + "，".join(parts) + "。红=出血，黄=硬性渗出，绿=软性渗出。",
    }


class LesionSegService:
    @staticmethod
    def run(db, user: User, case_id: int, image_url: str) -> dict:
        role = user.role.code if user.role else ""
        if role not in (RoleEnum.TEACHER.value, RoleEnum.ADMIN.value):
            raise HTTPException(status_code=403, detail="多病灶分割仅对带教老师和管理员开放")

        source = ReadingService.get_image_source(db=db, user=user, case_id=case_id)
        raw = (image_url or "").strip().split("?", 1)[0]
        if raw not in _allowed_urls(source):
            raise HTTPException(status_code=400, detail="这张图不属于当前病例")
        image_path = _resolve_static_file(raw)
        if image_path is None:
            raise HTTPException(status_code=400, detail="找不到这张眼底原图的文件")

        weight = _weight_file()
        if weight is None:
            return _empty("多病灶分割已接入，但权重文件 best_mdice.pth 不在服务器上。")
        if not ( _vendor_root() / "predict_multilesions.py").is_file():
            return _empty("多病灶分割已接入，但推理代码不在 backend/vendor/multi_lesions_seg。")

        try:
            return _infer(image_path, weight, case_id)
        except ModuleNotFoundError as exc:
            missing = getattr(exc, "name", None) or "依赖"
            return _empty(
                "多病灶分割已接入，当前环境还跑不起来。"
                f"缺少 {missing}。需要 PyTorch、scipy、einops、timm，"
                "以及 mamba_ssm 提供的 selective_scan（模型前向走这条路径）。"
            )
        except NameError as exc:
            if "selective_scan" in str(exc):
                return _empty(
                    "多病灶分割已接入，但 mamba_ssm 的 selective_scan 不可用。"
                    "只装 CPU 版 PyTorch 不够，模型前向需要这份算子。"
                )
            return _empty(f"多病灶分割没有完成：{exc}")
        except Exception as exc:
            return _empty(f"多病灶分割没有完成：{exc}")
