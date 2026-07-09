"""
一次性回填脚本
==============

1. 给所有 case_sn 为空的 ScreeningCase / TrainingCase 生成 case_sn
2. 把 image_paths 中的 URL 注册为 biz_case_image 的 role='original' 记录（去重）
3. 已经存在于 static/training/idrid/heatmaps/ 与 class_masks/ 的旧文件
   登记为 role='overlay' 与 'class_mask'

幂等：可重复跑。
"""

from __future__ import annotations

import sys
from pathlib import Path

_THIS = Path(__file__).resolve()
_BACKEND_ROOT = _THIS.parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


from app.core.config import settings
from app.db.models import (
    CaseImage,
    ScreeningCase,
    TrainingCase,
)
from app.db.session import SessionLocal
from app.services.case_image_service import CaseImageService
from app.services.case_sn import generate_case_sn


def _backfill_case_sn(db) -> int:
    n = 0
    for Model in (TrainingCase, ScreeningCase):
        rows = db.query(Model).filter(
            (Model.case_sn == None) | (Model.case_sn == "")  # noqa: E711
        ).all()
        for c in rows:
            c.case_sn = generate_case_sn(db)
            n += 1
        db.commit()
    return n


def _flatten(image_paths) -> list[str]:
    out = []
    if isinstance(image_paths, dict):
        for v in image_paths.values():
            if isinstance(v, list):
                out.extend([u for u in v if isinstance(u, str)])
    return out


def _register_existing_images(db) -> int:
    n = 0
    # 1) 主表 image_paths 中的所有 URL → role='original'
    for case_table, Model in (("training", TrainingCase), ("screening", ScreeningCase)):
        for c in db.query(Model).all():
            for url in _flatten(c.image_paths):
                if not url:
                    continue
                rec = CaseImageService.register_external(
                    db,
                    case_table=case_table, case_id=c.id,
                    role="original", eye="OU",
                    file_url=url,
                    file_name=url.rsplit("/", 1)[-1],
                )
                if rec is not None:
                    n += 1
    db.commit()

    # 2) 已落盘的 heatmaps / class_masks → role='overlay' / 'class_mask'
    static_url = settings.STATIC_URL
    upload_dir = Path(settings.UPLOAD_DIR)
    if not upload_dir.is_absolute():
        upload_dir = _BACKEND_ROOT / upload_dir
    idrid_root = upload_dir / "training" / "idrid"

    role_dirs = [
        ("overlay", idrid_root / "heatmaps"),
        ("class_mask", idrid_root / "class_masks"),
    ]
    for role, dir_ in role_dirs:
        if not dir_.exists():
            continue
        for f in dir_.iterdir():
            if not f.is_file():
                continue
            stem = f.stem.replace("_gold", "").replace("_class", "")
            # 通过文件名 IDRiD_XX → 找对应病例
            for case_table, Model in (("training", TrainingCase), ("screening", ScreeningCase)):
                col_no = f"IDRID-T-{stem}" if case_table == "training" else f"IDRID-P-{stem}"
                c = db.query(Model).filter(Model.case_no == col_no).first()
                if not c:
                    continue
                rel_url = f"{static_url}/training/idrid/{dir_.name}/{f.name}"
                rec = CaseImageService.register_external(
                    db,
                    case_table=case_table, case_id=c.id,
                    role=role, eye="OU",
                    file_url=rel_url,
                    file_name=f.name,
                    file_size=f.stat().st_size,
                )
                if rec is not None:
                    n += 1
    db.commit()
    return n


def main():
    db = SessionLocal()
    try:
        added_sn = _backfill_case_sn(db)
        print(f"已补 case_sn: {added_sn} 条")
        added_img = _register_existing_images(db)
        print(f"已登记影像记录: {added_img} 条")
        print(f"biz_case_image 总条数: {db.query(CaseImage).count()}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
