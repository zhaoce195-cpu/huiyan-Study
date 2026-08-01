# -*- coding: utf-8 -*-
"""
存量实训病例批量 DICOM 化

对应《慧眼医学培训端-重构技术方案》决策三「全量 DICOM 化」、
第 8.1 节「影像迁移」：

    1. 原图转 DICOM Ophthalmic Photography，写入患者标识、眼别、模态；
    2. mask / 金标准等派生对象本轮不转（应转 DICOM SEG，属后续工作），
       但会单独统计，避免被误认为漏转；
    3. 眼别冲突暴露为待人工确认清单，**不静默取值**
       —— 报告 8.3 首条 P0 用例；
    4. 转换幂等：UID 由病例与影像稳定派生，重跑不产生重复实例。

用法：
    # 预演（默认，不写文件）
    python scripts/convert_cases_to_dicom.py

    # 实际转换，输出到默认目录 app/static/dicom
    python scripts/convert_cases_to_dicom.py --apply

    # 指定范围与输出目录
    python scripts/convert_cases_to_dicom.py --apply --limit 5 --out /data/dicom

    # 放行眼别冲突（不推荐；仅在人工确认过之后使用）
    python scripts/convert_cases_to_dicom.py --apply --allow-laterality-conflict
"""

import argparse
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.common.dicom_convert import (  # noqa: E402
    LateralityConflictError,
    convert_image_to_dicom,
)
from app.common.image_safety import ORIGINAL_ROLE, role_text  # noqa: E402
from app.db.models import CaseImage, TrainingCase  # noqa: E402


def build_session(db_url: str):
    engine = create_engine(db_url, future=True)
    return sessionmaker(bind=engine, autoflush=False, future=True)()


def resolve_db_url(explicit: str = "") -> str:
    if explicit:
        return explicit
    try:
        from app.core.config import settings
        url = getattr(settings, "DATABASE_URL", "") or ""
        if url:
            return str(url)
    except Exception:
        pass
    return f"sqlite:///{(Path(__file__).resolve().parent.parent / 'edu_eye.db').as_posix()}"


def resolve_local_file(file_url: str) -> Path:
    """把 /static/... URL 还原为磁盘路径"""
    from app.core.config import settings

    raw = (file_url or "").split("?", 1)[0]
    prefix = settings.STATIC_URL.rstrip("/") + "/"
    rel = raw[len(prefix):] if raw.startswith(prefix) else raw.lstrip("/")
    base = Path(__file__).resolve().parent.parent / settings.UPLOAD_DIR
    return (base / rel).resolve()


def gender_to_dicom(g: str) -> str:
    return {"M": "M", "F": "F", "MALE": "M", "FEMALE": "F"}.get((g or "").upper(), "")


def main() -> int:
    parser = argparse.ArgumentParser(description="存量实训病例批量 DICOM 化")
    parser.add_argument("--apply", action="store_true", help="实际写出文件；不加则仅预演")
    parser.add_argument("--db", default="", help="数据库连接串")
    parser.add_argument("--out", default="", help="输出目录，默认 app/static/dicom")
    parser.add_argument("--limit", type=int, default=0, help="仅处理前 N 个病例")
    parser.add_argument("--allow-laterality-conflict", action="store_true",
                        help="放行眼别冲突（不推荐）")
    args = parser.parse_args()

    db_url = resolve_db_url(args.db)
    out_root = Path(args.out) if args.out else (
        Path(__file__).resolve().parent.parent / "app" / "static" / "dicom"
    )

    print(f"数据库：{db_url}")
    print(f"输出　：{out_root}")
    print(f"模式　：{'实际转换' if args.apply else '预演（不写文件）'}")
    print(f"眼别冲突：{'放行' if args.allow_laterality_conflict else '阻断并列入待确认清单'}")
    print("-" * 72)

    session = build_session(db_url)
    stats = {"cases": 0, "original": 0, "converted": 0,
             "derived_skipped": 0, "missing_file": 0, "conflict": 0, "failed": 0}
    conflicts = []
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
                .order_by(CaseImage.sort_order, CaseImage.id)
                .all()
            )

            originals = [i for i in images if i.role == ORIGINAL_ROLE]
            derived = [i for i in images if i.role != ORIGINAL_ROLE]
            stats["original"] += len(originals)
            stats["derived_skipped"] += len(derived)

            for idx, img in enumerate(originals, start=1):
                local = resolve_local_file(img.file_url or "")
                if not local.is_file():
                    stats["missing_file"] += 1
                    problems.append(f"[缺文件] 病例 {case.case_no} 影像#{img.id} {img.file_url}")
                    continue

                target = out_root / case.case_no / f"{img.id}.dcm"
                try:
                    if args.apply:
                        convert_image_to_dicom(
                            image_path=local,
                            output_path=target,
                            patient_id=case.case_no,
                            patient_name=case.patient_name or case.case_no,
                            patient_sex=gender_to_dicom(case.patient_gender),
                            case_no=case.case_no,
                            eye=img.eye,
                            file_name=img.file_name or local.name,
                            # 现有数据模型未采集真实检查时间，
                            # 此处留空而不是用入库时间冒充
                            exam_datetime=None,
                            instance_number=idx,
                            strict_laterality=not args.allow_laterality_conflict,
                        )
                    else:
                        # 预演也做眼别校验，好在写文件前就暴露问题
                        from app.common.image_safety import detect_laterality_conflict
                        c = detect_laterality_conflict(
                            eye=img.eye, file_name=img.file_name or local.name,
                        )
                        if c and not args.allow_laterality_conflict:
                            raise LateralityConflictError(c)
                    stats["converted"] += 1
                except LateralityConflictError as exc:
                    stats["conflict"] += 1
                    conflicts.append(
                        f"病例 {case.case_no} 影像#{img.id} {img.file_name or local.name}：{exc}"
                    )
                except Exception as exc:
                    stats["failed"] += 1
                    problems.append(f"[失败] 病例 {case.case_no} 影像#{img.id}：{exc}")
    finally:
        session.close()

    print(f"病例总数　　　　{stats['cases']}")
    print(f"原始影像　　　　{stats['original']}")
    print(f"{'已转换' if args.apply else '可转换'}　　　　　{stats['converted']}")
    print(f"派生对象（跳过）{stats['derived_skipped']}　← mask/overlay 应转 DICOM SEG，属后续工作")
    print(f"文件缺失　　　　{stats['missing_file']}")
    print(f"眼别冲突　　　　{stats['conflict']}")
    print(f"其他失败　　　　{stats['failed']}")

    if conflicts:
        print("-" * 72)
        print("眼别冲突待人工确认（未转换，系统不会自动选择其中一侧）：")
        for c in conflicts[:50]:
            print(f"  {c}")
        if len(conflicts) > 50:
            print(f"  ... 另有 {len(conflicts) - 50} 条")

    if problems:
        print("-" * 72)
        print("其他问题：")
        for p in problems[:30]:
            print(f"  {p}")
        if len(problems) > 30:
            print(f"  ... 另有 {len(problems) - 30} 条")

    if not args.apply:
        print("-" * 72)
        print("预演结束，未写出任何文件。确认无误后加 --apply 执行。")

    # 有冲突时以非零码退出，便于 CI / 运维脚本感知
    return 1 if (conflicts or stats["failed"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
