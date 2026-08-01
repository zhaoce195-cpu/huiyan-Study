# -*- coding: utf-8 -*-
"""
病灶掩码批量转 DICOM Segmentation

对应《医学培训端评估与工作流重构报告》P1：
    「影像与图层混算：『8 张/9 张影像』实际混合原图、mask、病灶层和金标准」

转换后每张原图对应：
    1 个 VL Photographic 实例（原始影像）
    1 个 SEG 实例（多分段，含该图全部病灶标注）
「影像」与「派生对象」在 DICOM 层面彻底分开，不会再被混算。

不参与转换的派生对象
    overlay / color_mask / class_mask 是渲染出来的可视化图，不是分割数据。
    它们可由原图 + SEG 随时重新渲染，不迁入 PACS，避免再次制造
    「说不清是什么」的影像条目。

用法：
    python scripts/convert_masks_to_seg.py              # 预演
    python scripts/convert_masks_to_seg.py --apply      # 实际生成
    python scripts/convert_masks_to_seg.py --apply --limit 5
"""

import argparse
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pydicom  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.common.dicom_seg import (  # noqa: E402
    RENDERED_ROLES,
    SEGMENTABLE_ROLES,
    build_seg,
    load_mask,
)
from app.db.models import CaseImage, TrainingCase  # noqa: E402


def build_session(db_url: str):
    return sessionmaker(bind=create_engine(db_url, future=True),
                        autoflush=False, future=True)()


def resolve_db_url(explicit=""):
    if explicit:
        return explicit
    try:
        from app.core.config import settings
        return str(settings.DATABASE_URL)
    except Exception:
        return f"sqlite:///{(Path(__file__).resolve().parent.parent / 'edu_eye.db').as_posix()}"


def local_path(file_url: str) -> Path:
    from app.core.config import settings
    raw = (file_url or "").split("?", 1)[0]
    prefix = settings.STATIC_URL.rstrip("/") + "/"
    rel = raw[len(prefix):] if raw.startswith(prefix) else raw.lstrip("/")
    return (Path(__file__).resolve().parent.parent / settings.UPLOAD_DIR / rel).resolve()


def main() -> int:
    p = argparse.ArgumentParser(description="病灶掩码批量转 DICOM SEG")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--db", default="")
    p.add_argument("--dicom-dir", default="app/static/dicom")
    p.add_argument("--limit", type=int, default=0)
    args = p.parse_args()

    dicom_root = Path(args.dicom_dir)
    print(f"原图目录：{dicom_root}")
    print(f"模式　　：{'实际生成' if args.apply else '预演（不写文件）'}")
    print(f"参与分割：{list(SEGMENTABLE_ROLES)}")
    print(f"跳过渲染：{list(RENDERED_ROLES)}（可由原图 + SEG 重新渲染）")
    print("-" * 72)

    session = build_session(resolve_db_url(args.db))
    stats = {"cases": 0, "seg": 0, "segments": 0,
             "no_mask": 0, "no_source": 0, "failed": 0, "rendered_skipped": 0}
    problems = []

    try:
        cases = session.query(TrainingCase).order_by(TrainingCase.id).all()
        if args.limit:
            cases = cases[:args.limit]

        for case in cases:
            stats["cases"] += 1
            images = (
                session.query(CaseImage)
                .filter(CaseImage.case_table == "training",
                        CaseImage.case_id == case.id)
                .all()
            )
            stats["rendered_skipped"] += sum(
                1 for i in images if i.role in RENDERED_ROLES)

            src_files = sorted((dicom_root / case.case_no).glob("*.dcm"))
            src_files = [f for f in src_files if not f.name.startswith("seg-")]
            if not src_files:
                stats["no_source"] += 1
                problems.append(f"[无原图 DICOM] {case.case_no}")
                continue
            source = pydicom.dcmread(str(src_files[0]))

            masks = {}
            for img in images:
                if img.role not in SEGMENTABLE_ROLES:
                    continue
                try:
                    m = load_mask(local_path(img.file_url or ""),
                                  shape=(source.Rows, source.Columns))
                except ValueError as exc:
                    problems.append(f"[尺寸不符] {case.case_no} {img.role}：{exc}")
                    continue
                if m is not None:
                    masks[img.role] = m

            if not masks:
                stats["no_mask"] += 1
                continue

            try:
                if args.apply:
                    seg = build_seg(source_dataset=source, masks=masks)
                    target = dicom_root / case.case_no / "seg-lesions.dcm"
                    seg.save_as(str(target), enforce_file_format=True)
                stats["seg"] += 1
                stats["segments"] += len(masks)
            except Exception as exc:
                stats["failed"] += 1
                problems.append(f"[生成失败] {case.case_no}：{type(exc).__name__} {exc}")
    finally:
        session.close()

    print(f"病例总数　　　　{stats['cases']}")
    print(f"{'已生成' if args.apply else '可生成'} SEG 实例　{stats['seg']}")
    print(f"分段总数　　　　{stats['segments']}")
    print(f"无有效掩码　　　{stats['no_mask']}")
    print(f"缺原图 DICOM　　{stats['no_source']}")
    print(f"渲染图跳过　　　{stats['rendered_skipped']}")
    print(f"失败　　　　　　{stats['failed']}")

    if problems:
        print("-" * 72)
        for x in problems[:20]:
            print(f"  {x}")
        if len(problems) > 20:
            print(f"  ... 另有 {len(problems) - 20} 条")

    if not args.apply:
        print("-" * 72)
        print("预演结束，未写出文件。确认后加 --apply 执行。")
    return 1 if stats["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
