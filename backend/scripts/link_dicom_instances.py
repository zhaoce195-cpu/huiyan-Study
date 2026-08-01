# -*- coding: utf-8 -*-
"""
影像记录 ↔ PACS 实例：回填对应关系 / 巡检失配

对应遗留清单 D-007。

回填（--apply）
    用当前本地路径重算 UID，与 PACS 中实际存在的实例核对，
    对得上才写库。对不上的一律不写 —— 写一个取不到像素的 UID，
    等于把「静默降级」换成「静默报错」，更糟。

巡检（默认）
    统计「本地有原图但 PACS 对不上」的数量。这个数字长期为 0 才正常；
    突然变大意味着影像目录搬过、或转换没跑全 ——
    没有这道巡检的话，表现只是阅片页悄悄退回 JPG，没人会发现。

用法：
    python scripts/link_dicom_instances.py            # 只巡检，不写库
    python scripts/link_dicom_instances.py --apply    # 回填
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.common.dicom_link import expected_uids  # noqa: E402
from app.db.models import CaseImage, TrainingCase  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.services import dicomweb_client  # noqa: E402

ORIGINAL_ROLE = "original"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="写库；缺省只巡检")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    db = SessionLocal()
    stats = {
        "cases": 0, "pacs_unreachable": 0, "originals": 0,
        "linked": 0, "already": 0, "unmatched": 0, "no_pacs_study": 0,
    }
    unmatched_samples = []

    try:
        cases = db.query(TrainingCase).order_by(TrainingCase.id).all()
        if args.limit:
            cases = cases[: args.limit]

        for case in cases:
            stats["cases"] += 1
            originals = (
                db.query(CaseImage)
                .filter(CaseImage.case_table == "training",
                        CaseImage.case_id == case.id,
                        CaseImage.role == ORIGINAL_ROLE)
                .order_by(CaseImage.sort_order, CaseImage.id)
                .all()
            )
            if not originals:
                continue
            stats["originals"] += len(originals)

            try:
                summary = dicomweb_client.study_summary(case.case_no)
            except Exception:
                # PACS 不可达是环境问题，不是数据问题，分开计数
                stats["pacs_unreachable"] += 1
                continue

            present = {i.get("sopInstanceUid") for i in summary.get("images", [])}
            if not present:
                stats["no_pacs_study"] += 1

            for img in originals:
                if img.sop_instance_uid:
                    stats["already"] += 1
                    continue
                uids = expected_uids(case.case_no, img.file_url or "", img.eye)
                if uids["sopInstanceUid"] not in present:
                    stats["unmatched"] += 1
                    if len(unmatched_samples) < 8:
                        unmatched_samples.append(
                            f"{case.case_no} 影像#{img.id} {img.file_url}"
                        )
                    continue
                if args.apply:
                    img.sop_instance_uid = uids["sopInstanceUid"]
                    img.series_instance_uid = uids["seriesInstanceUid"]
                    img.study_instance_uid = uids["studyInstanceUid"]
                stats["linked"] += 1

        if args.apply:
            db.commit()
    finally:
        db.close()

    print("=" * 58)
    print("回填" if args.apply else "巡检（未写库）")
    print("-" * 58)
    print(f"病例              {stats['cases']}")
    print(f"原图              {stats['originals']}")
    print(f"已有对应关系      {stats['already']}")
    print(f"{'本次写入' if args.apply else '可对应上'}          {stats['linked']}")
    print(f"PACS 中对不上     {stats['unmatched']}")
    print(f"PACS 无此 study   {stats['no_pacs_study']} 个病例")
    print(f"PACS 不可达       {stats['pacs_unreachable']} 个病例")
    if unmatched_samples:
        print("-" * 58)
        print("对不上的样例（影像目录搬迁或未转换）：")
        for s in unmatched_samples:
            print("  " + s)
    print("=" * 58)

    # 巡检模式下，有失配就以非 0 退出，便于接进定时任务告警
    return 1 if (not args.apply and stats["unmatched"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
