"""
IDRiD 多病灶数据集导入服务
=============================

复用模块：
- 命令行：python scripts/import_idrid.py
- 后台 API：POST /admin/import/idrid
均调用本文件的 :func:`run_idrid_import`

特性：
- 自动按文件名前缀（IDRiD_XX）归并到同一病例
- 复制原图 + 全部 5 种分割 mask + 3 种处理产物到 static/training/idrid/<role>/
- 写入 biz_case_image 一对多关联（ScreeningCase + TrainingCase 各登记一份）
- 自动生成 case_sn（CASE+yyyymmdd+6位）
- 启发式 DR 分级，输出统计
- 幂等：skip_existing=True 时按 case_no 跳过已存在病例
- 返回 IdridImportResult，含 sample_case_sns / 统计指标
"""

from __future__ import annotations

import json
import shutil
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    CaseImageRoleEnum,
    CaseImageTableEnum,
    GenderEnum,
    Role,
    RoleEnum,
    LearningNote,
    LearningResource,
    RotationTask,
    ScreeningCase,
    ScreeningStatusEnum,
    TrainingCase,
    User,
)
from app.db.models.training_case import (
    CaseArchiveStatusEnum,
    CaseCategoryEnum,
    CaseDifficultyEnum,
)
from app.schemas.case_image import IdridImportResult, IdridProbeResult
from app.services.case_image_service import CaseImageService
from app.services.case_sn import generate_case_sn
from app.services.patient_mock import generate_mock_patient


# ============================================================
# 约定目录
# ============================================================

REQUIRED_SUBDIRS = (
    "1. Original Images",
    "2. All Segmentation Groundtruths",
)

# 彩色掩膜、叠加图是后处理产物，官方数据包里没有这一层，缺了也能导入原图和分割掩膜。
OPTIONAL_SUBDIRS = (
    "3. IDRID_4_lesion_processed",
)

# 兼容旧脚本 import；实际解析请用 resolved_idrid_root()
DEFAULT_IDRID_ROOT = Path(r"d:\huiyan cloude\IDRID多病灶\IDRID多病灶")

LESION_CONFIGS = [
    {"name": "Microaneurysms", "folder": "1. Microaneurysms", "suffix": "MA",
     "code": "MA", "cn": "微血管瘤"},
    {"name": "Haemorrhages",   "folder": "2. Haemorrhages",   "suffix": "HE",
     "code": "HE", "cn": "出血"},
    {"name": "Hard Exudates",  "folder": "3. Hard Exudates",  "suffix": "EX",
     "code": "EX", "cn": "硬性渗出"},
    {"name": "Soft Exudates",  "folder": "4. Soft Exudates",  "suffix": "SE",
     "code": "SE", "cn": "软性渗出"},
    {"name": "Optic Disc",     "folder": "5. Optic Disc",     "suffix": "OD",
     "code": "OD", "cn": "视盘"},
]

SPLITS = [
    ("a. Training Set", "train"),
    ("b. Testing Set",  "test"),
]


# ============================================================
# 路径解析
# ============================================================

def _backend_root() -> Path:
    # app/services/idrid_import_service.py → backend
    return Path(__file__).resolve().parent.parent.parent


def _clean_source_text(raw: str) -> str:
    """去掉从资源管理器或聊天记录粘贴时带上的引号和 file://。"""
    text = (raw or "").strip()
    if text.lower().startswith("file:///"):
        text = text[8:]
        if len(text) >= 3 and text[0] == "/" and text[2] == ":":
            text = text[1:]
    elif text.lower().startswith("file://"):
        text = text[7:]
    text = text.strip().strip('"').strip("'").strip("「」").strip()
    if text.startswith("\\\\?\\"):
        text = text[4:]
    return text


def _is_idrid_root(path: Path) -> bool:
    return all((path / name).is_dir() for name in REQUIRED_SUBDIRS)


def _locate_idrid_root(start: Path) -> Optional[Path]:
    """
    用户常把路径指到数据包的上一层、下一层，或官方压缩包里的 A. Segmentation。
    只要附近能找到两个必备子目录，就用那个目录当根。
    """
    if not start.exists():
        return None
    if start.is_file():
        start = start.parent

    def nearby(path: Path) -> Optional[Path]:
        if _is_idrid_root(path):
            return path
        wrapped = path / "A. Segmentation"
        if wrapped.is_dir() and _is_idrid_root(wrapped):
            return wrapped
        try:
            children = [child for child in path.iterdir() if child.is_dir()]
        except OSError:
            return None
        for child in children:
            if _is_idrid_root(child):
                return child
            nested = child / "A. Segmentation"
            if nested.is_dir() and _is_idrid_root(nested):
                return nested
        return None

    found = nearby(start)
    if found is not None:
        return found
    current = start
    for _ in range(4):
        parent = current.parent
        if parent == current:
            break
        found = nearby(parent)
        if found is not None:
            return found
        current = parent
    return None


def _primary_source_path(source_path: Optional[str]) -> Path:
    text = _clean_source_text(source_path or "")
    if not text:
        text = (settings.IDRID_DATASET_ROOT or "data/idrid").strip()
    path = Path(text).expanduser()
    if path.is_absolute():
        return path
    return _backend_root() / path


def resolve_idrid_source(source_path: Optional[str] = None) -> Tuple[Optional[Path], Path]:
    """返回 (识别出的数据集根目录, 用来报错的原始路径)。"""
    primary = _primary_source_path(source_path)
    if primary.exists():
        return _locate_idrid_root(primary), primary
    if source_path and not Path(_clean_source_text(source_path)).is_absolute():
        other = Path.cwd() / _clean_source_text(source_path)
        if other.exists():
            return _locate_idrid_root(other), other
    return None, primary


def resolved_idrid_root(source_path: Optional[str] = None) -> Path:
    """服务端约定目录。相对路径相对 backend 根目录。"""
    located, primary = resolve_idrid_source(source_path)
    return located or primary


_LAYOUT_HINT = (
    "请填写运行后端的这台电脑上的 IDRiD 根目录，不要带引号。"
    "这个目录里应直接有「1. Original Images」和「2. All Segmentation Groundtruths」，"
    "官方压缩包多一层「A. Segmentation」也可以。"
    "「3. IDRID_4_lesion_processed」可以没有，没有时只导入原图和分割掩膜。"
)


def _list_split_images(img_dir: Path) -> List[Path]:
    if not img_dir.exists():
        return []
    return sorted(
        list(img_dir.glob("*.jpg"))
        + list(img_dir.glob("*.jpeg"))
        + list(img_dir.glob("*.png"))
    )


def probe_idrid_source(source_path: Optional[str] = None) -> IdridProbeResult:
    """只看目录结构与原图数量，不写库、不复制文件。"""
    default_path = str(_primary_source_path(None))
    located, primary = resolve_idrid_source(source_path)
    src_root = located or primary
    missing = [
        name for name in REQUIRED_SUBDIRS if not (src_root / name).exists()
    ]
    exists = primary.exists()
    train_count = 0
    test_count = 0
    if located is not None and not missing:
        img_root = src_root / "1. Original Images"
        train_count = len(_list_split_images(img_root / "a. Training Set"))
        test_count = len(_list_split_images(img_root / "b. Testing Set"))
    image_count = train_count + test_count
    ready = located is not None and not missing and image_count > 0
    if not exists:
        hint = f"没有这个目录：{primary}。{_LAYOUT_HINT}"
    elif located is None:
        hint = (
            f"目录存在：{primary}，但这里不是 IDRiD 根目录。"
            "需要能找到「1. Original Images」和「2. All Segmentation Groundtruths」。"
            "可以填数据集根目录，或它上面一层（例如里面有「A. Segmentation」的那一层）。"
        )
    elif image_count == 0:
        hint = (
            "必备子目录都在，但「1. Original Images」的 "
            "「a. Training Set」或「b. Testing Set」下没有 jpg/png。"
        )
    else:
        hint = (
            f"目录可用，共 {image_count} 张原图（训练 {train_count} / 测试 {test_count}）。"
            f"实际使用：{src_root}"
        )
    return IdridProbeResult(
        source_path=str(src_root),
        default_path=default_path,
        exists=exists,
        ready=ready,
        missing_subdirs=missing,
        image_count=image_count,
        train_count=train_count,
        test_count=test_count,
        hint=hint,
    )


def _dest_root() -> Tuple[Path, str]:
    """返回 (磁盘目录, 对外URL前缀)"""
    upload = settings.UPLOAD_DIR
    upload_path = Path(upload)
    if not upload_path.is_absolute():
        upload_path = _backend_root() / upload
    sub = "training/idrid"
    return upload_path / sub, f"{settings.STATIC_URL}/{sub}"


# ============================================================
# 工具
# ============================================================

def _find_mask(mask_dir: Path, stem: str, suffix: str) -> Optional[Path]:
    for ext in (".tif", ".TIF", ".png", ".jpg"):
        p = mask_dir / f"{stem}_{suffix}{ext}"
        if p.exists():
            return p
    g = list(mask_dir.glob(f"{stem}_{suffix}.*"))
    return g[0] if g else None


def _count_lesion_pixels(p: Path, threshold: int = 10) -> int:
    try:
        img = Image.open(p).convert("RGB")
        arr = np.array(img)
        return int(np.any(arr > threshold, axis=-1).sum())
    except Exception:
        return 0


# 国际临床分级（ICDR）的 4-2-1。棉绒斑、硬性渗出和出血像素都不是这条标准。
RULE_421 = (
    "四个象限中每个象限视网膜内出血都多于 20 处，"
    "或至少两个象限有明确的静脉串珠，"
    "或至少一个象限有明显的视网膜内微血管异常（IRMA）"
)
RULE_421_TEXT = (
    "重度非增殖性糖尿病视网膜病变（重度 NPDR）采用 4-2-1 标准："
    + RULE_421
    + "。三条里满足任何一条，并且没有新生血管，才是重度 NPDR。"
    "棉绒斑、硬性渗出或出血范围都不能单独写成重度 NPDR。"
    "没有新生血管不能诊断增殖性糖尿病视网膜病变（PDR）。"
)

# 掩膜只有 MA/HE/EX/SE/OD，看不到象限、静脉串珠、IRMA 和新生血管。
# 只有对过原图、确认有新生血管的病例才允许写成 PDR。
_REVIEWED_GRADE = {
    "IDRiD_17": {
        "grade": "4",
        "label": "PDR（NVE）",
        "conclusion": (
            "增殖性糖尿病视网膜病变（PDR）。上方血管弓旁可见扇形新生血管（NVE，位于视盘外）。"
            "下方可见舟状视网膜前积血，眼底结构仍可辨认，因此不把本例写成弥漫性玻璃体积血。"
            "视盘是否另有新生血管不能单凭此图定论，教学结论以明确的 NVE 为准。"
            "没有新生血管不能诊断 PDR。"
        ),
        "teaching": (
            "NVE 是长在视盘以外的新生血管，常沿血管弓呈扇形。"
            "视网膜前积血呈舟状、有液平面，后方的视网膜还能看见。"
            "玻璃体积血会把后极部蒙暗，血管看不清。"
            "视网膜前积血和玻璃体积血都不能代替新生血管。"
            "棉绒斑和出血再多，只要没有新生血管，就不能诊断 PDR。"
            "重度 NPDR 还要另满足 4-2-1，不能只凭出血或棉绒斑。"
        ),
    },
}

_GRADE_LABEL = {
    "0": "无 DR",
    "1": "轻度 NPDR",
    "2": "中度 NPDR",
    "3": "重度 NPDR",
    "4": "PDR",
}

_GRADE_CONCLUSION = {
    "0": "未见明显糖尿病视网膜病变征象。",
    "1": "轻度 NPDR：仅见微动脉瘤，无出血、硬性渗出或棉绒斑。",
    "2": "中度 NPDR：还没有核实到 4-2-1，也没有新生血管。",
    "3": "重度 NPDR：已满足 4-2-1 标准，并且没有新生血管。",
    "4": (
        "增殖性糖尿病视网膜病变（PDR）：必须见到新生血管。"
        "没有新生血管不能诊断 PDR。"
        "玻璃体积血或视网膜前出血不能代替新生血管。"
    ),
}

_GRADE_TEACHING = {
    "0": "正常眼底：视盘边界清楚，血管走形自然，没有微动脉瘤、出血、渗出或新生血管。",
    "1": "轻度 NPDR 只有微动脉瘤。一旦出现出血、硬性渗出或棉绒斑，就至少是中度 NPDR。",
    "2": RULE_421_TEXT,
    "3": RULE_421_TEXT,
    "4": (
        "增殖性糖尿病视网膜病变（PDR）必须见到视盘新生血管（NVD）或视盘外新生血管（NVE）。"
        "没有新生血管不能诊断 PDR。"
        "玻璃体积血或视网膜前出血不能代替新生血管。"
    ),
}

# 学员随机练习用的代表病例。中度和重度只用掩膜分级对得上、并且看过原图的编号。
_SPECTRUM_MODERATE = ("IDRiD_29", "IDRiD_43")
_SPECTRUM_SEVERE = ("IDRiD_35", "IDRiD_59", "IDRiD_25", "IDRiD_33")
_SPECTRUM_PDR = ("IDRiD_17",)
_SPECTRUM_MODERATE_TARGET = 4

IDRID_CLINICAL_NEUTRAL = "眼底彩色照片。请根据图像判断有没有糖尿病视网膜病变，以及轻到重的程度。"


def _count_of(lesions: Dict[str, int], *keys: str) -> int:
    total = 0
    for key in keys:
        try:
            total += int(lesions.get(key) or 0)
        except (TypeError, ValueError):
            continue
    return total


def _explicit_421(lesions: Dict[str, int]) -> List[str]:
    """只认已经按象限记下的 4-2-1。出血像素、棉绒斑不能代替。"""
    reasons: List[str] = []
    if _count_of(lesions, "HE4") >= 4:
        reasons.append("四个象限每个象限视网膜内出血都多于 20 处")
    if _count_of(lesions, "VB") >= 2:
        reasons.append("至少两个象限有明确的静脉串珠")
    if _count_of(lesions, "IRMA") >= 1:
        reasons.append("至少一个象限有明显的视网膜内微血管异常（IRMA）")
    return reasons


def _seen_neovascularization(lesions: Dict[str, int]) -> List[str]:
    seen: List[str] = []
    if _count_of(lesions, "NVD") > 0:
        seen.append("视盘新生血管（NVD）")
    if _count_of(lesions, "NVE") > 0:
        seen.append("视盘外新生血管（NVE）")
    if _count_of(lesions, "NV") > 0 and not seen:
        seen.append("新生血管")
    return seen


def _moderate_conclusion(lesions: Dict[str, int]) -> str:
    names = []
    if _count_of(lesions, "MA") > 0:
        names.append("微动脉瘤")
    if _count_of(lesions, "HE", "HM") > 0:
        names.append("视网膜出血")
    if _count_of(lesions, "EX") > 0:
        names.append("硬性渗出")
    if _count_of(lesions, "SE") > 0:
        names.append("棉绒斑")
    found = "、".join(names) if names else "视网膜病变"
    return (
        f"中度 NPDR：可见{found}。"
        "分割结果没有四个象限的出血计数，也没有静脉串珠或 IRMA，"
        "不能按 4-2-1 写成重度 NPDR。"
        "出血或棉绒斑再多也一样。"
        "没有新生血管，不能诊断 PDR。"
    )


def _severe_conclusion(reasons: List[str]) -> str:
    return (
        "重度 NPDR：已满足 4-2-1 标准（"
        + "；".join(reasons)
        + "），并且没有新生血管。"
        "棉绒斑和出血范围都不能单独作为这条诊断。"
    )


def _pdr_conclusion(seen: List[str]) -> str:
    what = "、".join(seen) if seen else "新生血管"
    return (
        f"增殖性糖尿病视网膜病变（PDR）：已见到{what}。"
        "没有新生血管不能诊断 PDR。"
        "玻璃体积血或视网膜前出血不能代替新生血管。"
    )


def grade_from_lesion_counts(
    lesions: Dict[str, int],
    stem: str = "",
) -> Tuple[str, str]:
    """
    由已记录的病灶给出 DR 0–4。

    掩膜像素不能证明 4-2-1，也不能证明新生血管。
    棉绒斑、大片出血都不单独写成重度 NPDR，更不能写成 PDR。
    """
    reviewed = _REVIEWED_GRADE.get(stem)
    if reviewed:
        return reviewed["grade"], reviewed["conclusion"]
    seen = _seen_neovascularization(lesions)
    if seen:
        return "4", _pdr_conclusion(seen)
    reasons = _explicit_421(lesions)
    if reasons:
        return "3", _severe_conclusion(reasons)
    he = _count_of(lesions, "HE", "HM")
    ex = _count_of(lesions, "EX")
    se = _count_of(lesions, "SE")
    ma = _count_of(lesions, "MA")
    if he > 0 or ex > 0 or se > 0:
        return "2", _moderate_conclusion(lesions)
    if ma > 0:
        return "1", _GRADE_CONCLUSION["1"]
    return "0", _GRADE_CONCLUSION["0"]


def _heuristic_grade(
    lesions: Dict[str, int],
    total_px: int,
    stem: str = "",
) -> Tuple[str, str]:
    del total_px  # 旧接口保留参数；分级改用绝对像素，避免小图比例失真
    return grade_from_lesion_counts(lesions, stem)


def _grade_label(grade: str, stem: str = "") -> str:
    reviewed = _REVIEWED_GRADE.get(stem)
    if reviewed:
        return reviewed["label"]
    return _GRADE_LABEL.get(grade, grade)


def _teaching_for(grade: str, stem: str = "") -> str:
    reviewed = _REVIEWED_GRADE.get(stem)
    if reviewed:
        return reviewed["teaching"]
    return _GRADE_TEACHING.get(grade, _GRADE_TEACHING["2"])


def _lesion_counts(gold_lesions) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for item in gold_lesions or []:
        if not isinstance(item, dict):
            continue
        code = str(item.get("type") or "")
        if not code:
            continue
        raw = item.get("pixel_count", item.get("count", 0))
        try:
            counts[code] = int(raw or 0)
        except (TypeError, ValueError):
            counts[code] = 0
    return counts


def _difficulty_for(grade: str) -> str:
    if grade in ("0", "1"):
        return CaseDifficultyEnum.EASY.value
    if grade == "2":
        return CaseDifficultyEnum.MEDIUM.value
    return CaseDifficultyEnum.HARD.value


def _get_creator(db: Session) -> User:
    u = (
        db.query(User)
        .join(Role, User.role_id == Role.id)
        .filter(Role.code.in_([RoleEnum.ADMIN.value, RoleEnum.TEACHER.value]))
        .first()
    )
    if not u:
        raise RuntimeError("数据库无 ADMIN/TEACHER 用户，请先 seed_demo")
    return u


def _ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def _safe_copy(src: Path, dst: Path) -> int:
    """复制并返回文件大小（字节）。已存在则跳过复制但返回大小。"""
    if not dst.exists():
        shutil.copy2(src, dst)
    try:
        return dst.stat().st_size
    except Exception:
        return 0


# ============================================================
# 主流程
# ============================================================

def run_idrid_import(
    db: Session,
    *,
    source_path: Optional[str] = None,
    limit: Optional[int] = None,
    dry_run: bool = False,
    skip_existing: bool = True,
    creator: Optional[User] = None,
    dest_root: Optional[Path] = None,
) -> IdridImportResult:
    located, primary = resolve_idrid_source(source_path)
    if located is None:
        if not primary.exists():
            raise FileNotFoundError(f"没有这个目录：{primary}。{_LAYOUT_HINT}")
        raise FileNotFoundError(
            f"目录存在：{primary}，但这里不是 IDRiD 根目录。"
            "需要能找到「1. Original Images」和「2. All Segmentation Groundtruths」。"
            "可以填数据集根目录，或它上面一层。"
        )
    src_root = located
    src_img_root = src_root / "1. Original Images"
    src_gt_root = src_root / "2. All Segmentation Groundtruths"
    src_proc_root = src_root / "3. IDRID_4_lesion_processed"

    if dest_root is not None:
        dest_root, url_prefix = Path(dest_root), f"{settings.STATIC_URL}/training/idrid"
    else:
        dest_root, url_prefix = _dest_root()
    # 子目录：originals + 9 个 role
    role_subdirs = {
        "originals": dest_root / "originals",
        "MA":         dest_root / "MA",
        "HE":         dest_root / "HE",
        "EX":         dest_root / "EX",
        "SE":         dest_root / "SE",
        "OD":         dest_root / "OD",
        "color_mask": dest_root / "color_mask",
        "overlay":    dest_root / "overlay",
        "class_mask": dest_root / "class_masks",
    }
    if not dry_run:
        for p in role_subdirs.values():
            _ensure_dir(p)

    creator = creator or _get_creator(db)
    creator_id = creator.id

    started = time.time()
    imported = 0
    skipped = 0
    appended_images = 0
    incomplete_count = 0
    grade_dist: Counter[str] = Counter()
    sample_sns: List[str] = []

    seq = 0
    for split_dir_name, split_tag in SPLITS:
        img_dir = src_img_root / split_dir_name
        gt_split = src_gt_root / split_dir_name
        overlay_dir = src_proc_root / "overlay_on_image" / split_dir_name
        class_dir = src_proc_root / "class_index_mask" / split_dir_name
        color_dir = src_proc_root / "color_mask" / split_dir_name
        if not img_dir.exists():
            continue

        images = _list_split_images(img_dir)

        for img_path in images:
            if limit and seq >= limit:
                break
            seq += 1
            stem = img_path.stem
            case_no_t = f"IDRID-T-{stem}"
            case_no_s = f"IDRID-P-{stem}"

            existing_t = (
                db.query(TrainingCase).filter(TrainingCase.case_no == case_no_t).first()
            )
            existing_s = (
                db.query(ScreeningCase).filter(ScreeningCase.case_no == case_no_s).first()
            )

            if skip_existing and existing_t and existing_s:
                skipped += 1
                continue

            # 计算病灶像素 + DR 分级
            with Image.open(img_path) as im:
                w, h = im.size
            total_px = w * h
            counts: Dict[str, int] = {}
            for cfg in LESION_CONFIGS:
                if cfg["code"] in ("OD",):  # OD 不参与分级
                    counts.setdefault(cfg["code"], 0)
                    continue
                p = _find_mask(gt_split / cfg["folder"], stem, cfg["suffix"])
                counts[cfg["code"]] = _count_lesion_pixels(p) if p else 0
            grade, conclusion = _heuristic_grade(counts, total_px, stem)
            grade_dist[grade] += 1

            if dry_run:
                imported += 1
                continue

            # ============ 复制文件 + 生成 URL 列表 ============
            files_to_copy: List[Tuple[str, Path, Path]] = []
            # original
            files_to_copy.append((
                "original", img_path, role_subdirs["originals"] / f"{stem}.jpg",
            ))
            for cfg in LESION_CONFIGS:
                p = _find_mask(gt_split / cfg["folder"], stem, cfg["suffix"])
                if p:
                    files_to_copy.append((
                        cfg["code"], p, role_subdirs[cfg["code"]] / f"{stem}_{cfg['suffix']}.png",
                    ))
            # processed
            color_p = color_dir / f"{stem}_color_mask.png"
            if color_p.exists():
                files_to_copy.append((
                    "color_mask", color_p, role_subdirs["color_mask"] / color_p.name,
                ))
            overlay_p = overlay_dir / f"{stem}_overlay.png"
            if overlay_p.exists():
                files_to_copy.append((
                    "overlay", overlay_p, role_subdirs["overlay"] / overlay_p.name,
                ))
            class_p = class_dir / f"{stem}_class_mask.png"
            if class_p.exists():
                files_to_copy.append((
                    "class_mask", class_p, role_subdirs["class_mask"] / class_p.name,
                ))

            url_records: List[Tuple[str, str, str, int]] = []  # (role, url, fname, size)
            for role, src, dst in files_to_copy:
                # mask tif → 落盘 png 更适合浏览器；这里 tif 直接转 png
                if src.suffix.lower() in (".tif", ".tiff") and dst.suffix.lower() == ".png":
                    if not dst.exists():
                        try:
                            with Image.open(src) as im:
                                im.convert("RGB").save(dst, format="PNG")
                        except Exception:
                            shutil.copy2(src, dst)
                    size = dst.stat().st_size if dst.exists() else 0
                else:
                    size = _safe_copy(src, dst)
                url = f"{url_prefix}/{dst.parent.name}/{dst.name}"
                url_records.append((role, url, dst.name, size))

            # ============ 主表 ============
            # 一次性生成模拟患者信息：双表共用同一份（同一个真实患者）
            patient = generate_mock_patient(db)

            tc = existing_t
            if not tc:
                tc = TrainingCase(
                    case_no=case_no_t,
                    title=f"{stem} · {_grade_label(grade, stem)}",
                    description=(
                        f"来源：IDRiD 多病灶分割（{split_tag}）\n"
                        f"金标准 DR 分级：{grade}（{_grade_label(grade, stem)}）\n"
                        f"病灶检出：" + (
                            ", ".join(f"{k}:{v}px" for k, v in counts.items() if v > 0) or "无"
                        )
                    ),
                    category=CaseCategoryEnum.DR.value,
                    difficulty=_difficulty_for(grade),
                    patient_name=patient.name,
                    patient_age=patient.age,
                    patient_gender=patient.gender,
                    patient_phone=patient.phone,
                    clinical_info=IDRID_CLINICAL_NEUTRAL,
                    image_paths={"OU": [url_records[0][1]]} if url_records else {},
                    gold_dr_grade=grade,
                    gold_diagnosis=conclusion,
                    gold_lesions=[
                        {"type": k, "pixel_count": v}
                        for k, v in counts.items() if v > 0
                    ],
                    gold_annotations=[],
                    gold_heatmap_path=next(
                        (u for r, u, _, _ in url_records if r == "overlay"), "",
                    ),
                    teaching_points=_teaching_for(grade, stem),
                    pass_score=60,
                    is_published=False,
                    is_train_case=False,
                    archive_status=CaseArchiveStatusEnum.ACTIVE.value,
                    creator_id=creator_id,
                )
                db.add(tc)
                db.flush()
            else:
                # 已存在但未填模拟患者信息：补齐
                if not tc.patient_name:
                    tc.patient_name = patient.name
                    tc.patient_gender = patient.gender
                    tc.patient_age = patient.age
                    tc.patient_phone = patient.phone
            if not tc.case_sn:
                tc.case_sn = generate_case_sn(db)

            sc = existing_s
            if not sc:
                sc = ScreeningCase(
                    case_no=case_no_s,
                    patient_name=patient.name,
                    patient_id_card="",
                    gender=patient.gender,
                    age=patient.age,
                    phone=patient.phone,
                    patient_phone=patient.phone,
                    chief_complaint=f"IDRiD 数据集脱敏样本（{split_tag}）",
                    medical_history=conclusion,
                    diabetes_years=None,
                    image_paths={"OU": [url_records[0][1]]} if url_records else {},
                    image_count=1,
                    status=ScreeningStatusEnum.PENDING.value,
                    report_status="pending",
                    report_pdf_path="",
                    patient_user_id=None,
                    department_id=None,
                    submit_user_id=creator_id,
                    review_user_id=None,
                    submit_at=datetime.now(),
                    review_at=None,
                    remark=f"IDRiD/{split_tag}/{stem}",
                )
                db.add(sc)
                db.flush()
            else:
                if not sc.patient_name or sc.patient_name.startswith("IDRiD-"):
                    sc.patient_name = patient.name
                    sc.gender = patient.gender
                    sc.age = patient.age
                    sc.phone = patient.phone
                    sc.patient_phone = patient.phone
            if not sc.case_sn:
                sc.case_sn = generate_case_sn(db)

            # ============ biz_case_image 多对多登记 ============
            for role, url, fname, size in url_records:
                for tbl, cid in (("training", tc.id), ("screening", sc.id)):
                    rec = CaseImageService.register_external(
                        db,
                        case_table=tbl, case_id=cid,
                        role=role, eye="UK",
                        file_url=url, file_name=fname, file_size=size,
                        uploaded_by=creator_id,
                    )
                    if rec is not None:
                        appended_images += 1

            # 完整性
            comp = CaseImageService.case_completeness(
                db, case_table="training", case_id=tc.id,
            )
            if not comp["complete"]:
                incomplete_count += 1

            if tc.case_sn and len(sample_sns) < 3:
                sample_sns.append(tc.case_sn)

            imported += 1
            if imported % 10 == 0:
                db.commit()

        if limit and seq >= limit:
            break

    if dry_run:
        db.rollback()
    else:
        db.commit()

    elapsed = time.time() - started

    return IdridImportResult(
        imported_cases=imported,
        appended_images=appended_images,
        skipped_cases=skipped,
        incomplete_cases=incomplete_count,
        grade_distribution=dict(grade_dist),
        elapsed_sec=round(elapsed, 2),
        dry_run=dry_run,
        sample_case_sns=sample_sns,
        source_path=str(src_root),
    )


def _idrid_stem(case_no: str) -> str:
    prefix = "IDRID-T-"
    if case_no.startswith(prefix):
        return case_no[len(prefix):]
    return ""


def _spectrum_stems(graded: Dict[str, Tuple[str, int]]) -> set:
    """graded: 文件名 -> (分级, 出血像素)。只把分级对得上的代表病例放进学员库。"""
    chosen = set()
    for stem in _SPECTRUM_PDR:
        if graded.get(stem, ("", 0))[0] == "4":
            chosen.add(stem)
    for stem in _SPECTRUM_SEVERE:
        if graded.get(stem, ("", 0))[0] == "3":
            chosen.add(stem)
    moderates = [
        stem for stem in _SPECTRUM_MODERATE
        if graded.get(stem, ("", 0))[0] == "2"
    ]
    extras = sorted(
        (
            (he, stem)
            for stem, (grade, he) in graded.items()
            if grade == "2" and stem not in moderates
        )
    )
    for stem in moderates:
        chosen.add(stem)
    need = _SPECTRUM_MODERATE_TARGET - len(moderates)
    for _he, stem in extras[: max(0, need)]:
        chosen.add(stem)
    return chosen


def _strip_neovascular_marks(case: TrainingCase) -> None:
    case.gold_annotations = [
        ann for ann in (case.gold_annotations or [])
        if not (isinstance(ann, dict) and "新生血管" in str(ann.get("label") or ""))
    ]
    case.gold_lesions = [
        item for item in (case.gold_lesions or [])
        if not (isinstance(item, dict) and str(item.get("type") or "") in {"NV", "NVD", "NVE"})
    ]


def _keep_seed_endpoints_in_pool(db: Session) -> None:
    """正常眼底和轻度 NPDR 这套分割图里没有，继续用已有教学示例。"""
    for case_no in ("T2026001", "T2026002"):
        row = db.query(TrainingCase).filter(TrainingCase.case_no == case_no).first()
        if row is None:
            continue
        if row.archive_status != CaseArchiveStatusEnum.ACTIVE.value:
            continue
        row.is_published = True
        row.is_train_case = True


def _correct_demo_labels(db: Session) -> List[str]:
    """示例图上没有新生血管，去掉写错的 NVD / 玻璃体积血结论。不改已有练习成绩。"""
    notes: List[str] = []
    severe = db.query(TrainingCase).filter(TrainingCase.case_no == "T2026004").first()
    if severe is not None:
        _strip_neovascular_marks(severe)
        diagnosis = severe.gold_diagnosis or ""
        if (
            diagnosis in ("", "重度 NPDR，4 象限均见出血，疑似静脉串珠")
            or "疑似静脉串珠" in diagnosis
            or "4 象限均见出血" in diagnosis
        ):
            severe.gold_diagnosis = (
                "重度 NPDR：记录为两个象限静脉串珠、一个象限 IRMA，没有新生血管。"
                "出血没有按四个象限分别计数，不能写成每个象限多于 20 处。"
            )
        teaching = severe.teaching_points or ""
        if "每个象限视网膜内出血都多于 20" not in teaching:
            teaching = RULE_421_TEXT
        note = "本示例图不作为新生血管（NVD/NVE）教学。"
        if note not in teaching:
            teaching = (teaching.rstrip() + "\n" + note).strip()
        severe.teaching_points = teaching
        notes.append("T2026004")
    pdr = db.query(TrainingCase).filter(TrainingCase.case_no == "T2026005").first()
    if pdr is not None:
        pdr.gold_dr_grade = "2"
        pdr.title = "中度 NPDR（教学示例）"
        pdr.gold_diagnosis = (
            "中度 NPDR：少量微动脉瘤与小簇硬性渗出。"
            "本图未见视盘或视盘外新生血管，也未见玻璃体积血。"
        )
        pdr.clinical_info = "糖尿病史。请按眼底图判读。"
        pdr.teaching_points = (
            "这张示例图只有少量微动脉瘤和硬性渗出，按中度 NPDR。"
            "图上没有新生血管，也没有蒙住眼底的玻璃体积血，不能判成 PDR。"
        )
        pdr.difficulty = CaseDifficultyEnum.MEDIUM.value
        pdr.description = "教学示例。金标准已按图像改回中度 NPDR，不再标成视盘新生血管。"
        _strip_neovascular_marks(pdr)
        pdr.gold_lesions = [{"type": "MA", "count": 4}, {"type": "EX", "count": 1}]
        pdr.is_train_case = False
        pdr.is_published = False
        notes.append("T2026005")
    return notes


def _apply_grade_language(text: str, *, explain: bool = False) -> str:
    """把含糊的 4-2-1 和「前增殖期」换成国际临床分级的说法。"""
    if not text:
        return text
    replacements = (
        (
            "棉绒斑属于重度非增殖期，不能据此诊断增殖期。",
            "棉绒斑不是 4-2-1 标准，不能单独写成重度 NPDR。没有新生血管不能诊断 PDR。",
        ),
        (
            "须见到新生血管或玻璃体积血。",
            "必须见到新生血管。没有新生血管不能诊断 PDR。玻璃体积血不能代替新生血管。",
        ),
        (
            "符合 4-2-1 法则任一即诊断重度 NPDR：4 象限出血/2 象限静脉串珠/1 象限 IRMA。",
            RULE_421_TEXT,
        ),
        (
            "4 个象限出血，或 2 个象限静脉串珠，或 1 个象限 IRMA",
            RULE_421,
        ),
        (
            "四个象限较多出血、至少两个象限静脉串珠，或一个象限 IRMA",
            RULE_421,
        ),
        (
            "- 4 象限均有出血\n- 2 象限静脉串珠\n- 1 象限 IRMA\n符合任一即为重度。",
            RULE_421_TEXT,
        ),
        (
            "| 3 | 重度 NPDR | 4-2-1 法则任一 |",
            "| 3 | 重度 NPDR | 4-2-1 标准，且没有新生血管 |",
        ),
        ("前增殖期", "重度 NPDR"),
        ("重度非增殖期", "重度 NPDR"),
        (
            "分清正常眼底、轻度到重度 NPDR，以及增殖期的新生血管和视网膜前积血。",
            "分清正常眼底、轻度到重度 NPDR。增殖性糖尿病视网膜病变（PDR）必须见到新生血管，视网膜前积血不能代替新生血管。",
        ),
        (
            "必学知识点：糖网从正常到增殖期",
            "必学知识点：糖网从正常眼底到 PDR",
        ),
    )
    for old, new in replacements:
        text = text.replace(old, new)
    if explain and "4-2-1" in text and "每个象限视网膜内出血都多于 20" not in text:
        text = text.rstrip() + "\n\n" + RULE_421_TEXT
    return text


def _correct_grade_language(db: Session) -> int:
    """改学习资料、笔记和仍写着旧说法的病例。不改已经记下的练习成绩。"""
    changed = 0
    for row in db.query(LearningResource).all():
        summary = _apply_grade_language(row.summary or "")
        content = _apply_grade_language(row.content or "", explain=True)
        if summary != (row.summary or "") or content != (row.content or ""):
            row.summary = summary
            row.content = content
            changed += 1
    for row in db.query(LearningNote).all():
        content = _apply_grade_language(row.content or "", explain=True)
        if content != (row.content or ""):
            row.content = content
            changed += 1
    for row in db.query(RotationTask).all():
        title = _apply_grade_language(row.title or "")
        summary = _apply_grade_language(row.summary or "")
        if title != (row.title or "") or summary != (row.summary or ""):
            row.title = title
            row.summary = summary
            changed += 1
    for row in db.query(TrainingCase).filter(~TrainingCase.case_no.like("IDRID-T-%")).all():
        diagnosis = _apply_grade_language(row.gold_diagnosis or "")
        teaching = _apply_grade_language(row.teaching_points or "", explain=True)
        if diagnosis != (row.gold_diagnosis or "") or teaching != (row.teaching_points or ""):
            row.gold_diagnosis = diagnosis
            row.teaching_points = teaching
            changed += 1
    return changed


def refresh_idrid_spectrum(db: Session) -> Dict[str, object]:
    """
    按掩膜重写 IDRiD 金标准分级，并放出一条从中度到 PDR 的学员练习谱。

    只改病例上的分级、诊断和是否进入实训库。不改练习会话里已经记下的分数。
    """
    cases = (
        db.query(TrainingCase)
        .filter(TrainingCase.case_no.like("IDRID-T-%"))
        .all()
    )
    graded: Dict[str, Tuple[str, int]] = {}
    paired: List[Tuple[str, TrainingCase]] = []
    for case in cases:
        stem = _idrid_stem(case.case_no)
        counts = _lesion_counts(case.gold_lesions)
        grade, conclusion = grade_from_lesion_counts(counts, stem)
        label = _grade_label(grade, stem)
        case.gold_dr_grade = grade
        case.gold_diagnosis = conclusion
        case.clinical_info = IDRID_CLINICAL_NEUTRAL
        case.teaching_points = _teaching_for(grade, stem)
        case.difficulty = _difficulty_for(grade)
        case.title = f"{stem} · {label}"[:128]
        detected = ", ".join(
            f"{k}:{v}px" for k, v in counts.items() if v > 0 and k != "OD"
        ) or "无"
        case.description = (
            f"来源：IDRiD 多病灶分割\n"
            f"金标准 DR 分级：{grade}（{label}）\n"
            f"病灶检出：{detected}"
        )
        graded[stem] = (grade, int(counts.get("HE") or 0))
        paired.append((stem, case))
        screening = (
            db.query(ScreeningCase)
            .filter(ScreeningCase.case_no == f"IDRID-P-{stem}")
            .first()
        )
        if screening is not None:
            screening.medical_history = conclusion

    chosen = _spectrum_stems(graded)
    for stem, case in paired:
        in_pool = (
            stem in chosen
            and case.archive_status == CaseArchiveStatusEnum.ACTIVE.value
        )
        case.is_published = in_pool
        case.is_train_case = in_pool
    _keep_seed_endpoints_in_pool(db)
    demo_notes = _correct_demo_labels(db)
    wording = _correct_grade_language(db)
    db.commit()
    return {
        "updated": len(cases),
        "grade_distribution": dict(Counter(grade for grade, _he in graded.values())),
        "train_distribution": dict(
            Counter(grade for stem, (grade, _he) in graded.items() if stem in chosen)
        ),
        "train_stems": sorted(chosen),
        "demo_adjusted": demo_notes,
        "wording_updated": wording,
    }


__all__ = [
    "run_idrid_import",
    "probe_idrid_source",
    "refresh_idrid_spectrum",
    "grade_from_lesion_counts",
    "resolved_idrid_root",
    "DEFAULT_IDRID_ROOT",
]
