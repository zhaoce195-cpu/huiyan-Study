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


def resolved_idrid_root(source_path: Optional[str] = None) -> Path:
    """服务端约定目录。相对路径相对 backend 根目录。"""
    raw = (source_path or settings.IDRID_DATASET_ROOT or "data/idrid").strip()
    p = Path(raw)
    if not p.is_absolute():
        p = _backend_root() / p
    return p


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
    default_path = str(resolved_idrid_root())
    src_root = resolved_idrid_root(source_path)
    missing = [
        name for name in REQUIRED_SUBDIRS if not (src_root / name).exists()
    ]
    exists = src_root.exists()
    train_count = 0
    test_count = 0
    if exists and not missing:
        img_root = src_root / "1. Original Images"
        train_count = len(_list_split_images(img_root / "a. Training Set"))
        test_count = len(_list_split_images(img_root / "b. Testing Set"))
    image_count = train_count + test_count
    ready = exists and not missing and image_count > 0
    if not exists:
        hint = (
            f"服务端还没有这个目录。请运维把 IDRiD 数据集放到：{src_root}"
            "（容器部署时还需挂载进容器）。"
        )
    elif missing:
        hint = f"目录在，但缺少子目录：{'、'.join(missing)}。请确认填的是数据集根目录。"
    elif image_count == 0:
        hint = "三个子目录都在，但 Original Images 下没有 jpg/png。"
    else:
        hint = f"约定目录就绪，共 {image_count} 张原图（训练 {train_count} / 测试 {test_count}）。"
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


def _heuristic_grade(lesions: Dict[str, int], total_px: int) -> Tuple[str, str]:
    has = {k: v > 0 for k, v in lesions.items()}
    ratio = {k: v / max(1, total_px) for k, v in lesions.items()}
    if has.get("SE"):
        return "4", "增殖性 / 进展期 DR：检出软性渗出（CWS），结合其他征象判读"
    if has.get("HE") and ratio.get("HE", 0) > 0.001:
        return "3", "重度 NPDR：大面积视网膜出血"
    if has.get("HE") or (has.get("EX") and ratio.get("EX", 0) > 0.0015):
        return "3", "重度 NPDR：明显出血或硬性渗出"
    if has.get("EX"):
        return "2", "中度 NPDR：检出硬性渗出"
    if has.get("MA"):
        return "1", "轻度 NPDR：仅见微血管瘤"
    return "0", "未见明显 DR 征象"


def _difficulty_for(grade: str) -> str:
    if grade in ("0", "1"):
        return CaseDifficultyEnum.EASY.value
    if grade in ("2", "3"):
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
    src_root = resolved_idrid_root(source_path)
    if not src_root.exists():
        # 管理员常把自己电脑上的路径填进来（测试报告：「填了正确的本地路径，
        # 系统提示找不到」）。这个路径是在**服务端**解析的，说清楚，
        # 免得对着一个确实存在的本地目录反复重试。
        raise FileNotFoundError(
            f"服务端找不到该目录：{src_root}\n"
            "注意：这里填的是**运行后端的服务器上**的路径，不是你本机的路径；"
            "数据集需要先放到服务器约定目录（容器部署时还要挂载进容器）。\n"
            f"未填写时使用的约定路径为：{resolved_idrid_root()}\n"
            "目录下应当包含：「1. Original Images」「2. All Segmentation Groundtruths」"
            "「3. IDRID_4_lesion_processed」三个子目录。"
        )

    src_img_root = src_root / "1. Original Images"
    src_gt_root = src_root / "2. All Segmentation Groundtruths"
    src_proc_root = src_root / "3. IDRID_4_lesion_processed"
    missing = [
        p.name for p in (src_img_root, src_gt_root, src_proc_root) if not p.exists()
    ]
    if missing:
        # 目录在、但结构不对时，早点说清缺哪个，比跑到一半报空结果强
        raise FileNotFoundError(
            f"源目录 {src_root} 下缺少子目录：{'、'.join(missing)}。"
            "请确认填的是 IDRiD 数据集的根目录。"
        )

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
            grade, conclusion = _heuristic_grade(counts, total_px)
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
                    title=f"IDRiD {stem} · DR {grade} 级",
                    description=(
                        f"来源：IDRiD 多病灶分割（{split_tag}）\n"
                        f"金标准 DR 分级：{grade}\n"
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
                    clinical_info=conclusion,
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
                    teaching_points=(
                        "教学要点：MA 多见于轻度；EX 反映慢性渗漏；HE 大面积出血提示重度；SE 警惕前增殖期。"
                    ),
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
                        role=role, eye="OU",
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


__all__ = [
    "run_idrid_import",
    "probe_idrid_source",
    "resolved_idrid_root",
    "DEFAULT_IDRID_ROOT",
]
