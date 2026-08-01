# -*- coding: utf-8 -*-
"""
由视盘（OD）分割掩码推断眼别并回填

背景
    存量 88 张原始影像的 eye 字段全部是 'OU'，文件名也无任何眼别线索，
    导致 DICOM 化后 ImageLaterality 一律缺失、安全条上只能显示「眼别未知」，
    报告要求的「三秒安全核对」无法满足。

方法
    视盘位于黄斑鼻侧，因此视盘在图像中的左右位置直接反映眼别。
    IDRiD 数据集随附视盘分割掩码，取其质心横坐标与图像中心比较即可分组。
    实测 81 张呈清晰双峰分布（43 例偏左、38 例偏右），
    落在模糊带（0.4~0.6）的仅 2 张，会被单独列出交人工判定。

重要
    「视盘在右 = 哪只眼」这个映射必须由人确认后通过 --disc-right-is 显式指定。
    脚本不设默认值——把整个数据集的眼别标反，正是本次整改要防的「看错眼」。
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

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.db.models import CaseImage  # noqa: E402

Image.MAX_IMAGE_PIXELS = None

# 模糊带：质心落在此区间时不自动判定，交人工确认
AMBIGUOUS_LOW, AMBIGUOUS_HIGH = 0.40, 0.60


def build_session(db_url: str):
    return sessionmaker(bind=create_engine(db_url, future=True),
                        autoflush=False, future=True)()


def resolve_db_url(explicit: str = "") -> str:
    if explicit:
        return explicit
    try:
        from app.core.config import settings
        if getattr(settings, "DATABASE_URL", ""):
            return str(settings.DATABASE_URL)
    except Exception:
        pass
    return f"sqlite:///{(Path(__file__).resolve().parent.parent / 'edu_eye.db').as_posix()}"


def disc_x_ratio(mask_path: Path) -> float:
    """视盘质心横坐标占图像宽度的比例；掩码为空时返回 -1"""
    with Image.open(mask_path) as im:
        arr = np.asarray(im.convert("L"))
    ys, xs = np.nonzero(arr > 0)
    if len(xs) == 0:
        return -1.0
    return float(xs.mean() / arr.shape[1])


def main() -> int:
    p = argparse.ArgumentParser(description="由视盘掩码推断眼别并回填")
    p.add_argument("--disc-right-is", choices=["OD", "OS"], required=True,
                   help="视盘位于图像右侧时对应的眼别（须经人工/临床确认）")
    p.add_argument("--mask-dir", default="app/static/training/idrid/OD",
                   help="视盘掩码目录")
    p.add_argument("--apply", action="store_true", help="实际写库；不加则预演")
    p.add_argument("--no-propagate", action="store_true",
                   help="不把眼别传播给该病例的派生对象（mask/overlay）")
    p.add_argument("--db", default="")
    args = p.parse_args()

    disc_right = args.disc_right_is
    disc_left = "OS" if disc_right == "OD" else "OD"

    mask_dir = Path(args.mask_dir)
    if not mask_dir.is_dir():
        print(f"掩码目录不存在：{mask_dir}", file=sys.stderr)
        return 1

    print(f"掩码目录　　：{mask_dir}")
    print(f"映射　　　　：视盘在右 → {disc_right}　视盘在左 → {disc_left}")
    print(f"模式　　　　：{'实际写库' if args.apply else '预演（不写库）'}")
    print("-" * 70)

    # 掩码文件名形如 IDRiD_01_OD.png，对应原图 IDRiD_01.jpg
    ratios = {}
    for f in sorted(mask_dir.glob("*.png")):
        stem = f.stem[:-3] if f.stem.endswith("_OD") else f.stem
        ratios[stem] = disc_x_ratio(f)

    session = build_session(resolve_db_url(args.db))
    updated = ambiguous = unmatched = empty = propagated = 0
    amb_list, unmatched_list = [], []
    case_eye = {}   # case_id -> 由原图判定出的眼别，用于传播给派生对象

    try:
        images = (
            session.query(CaseImage)
            .filter(CaseImage.case_table == "training",
                    CaseImage.role == "original")
            .order_by(CaseImage.id)
            .all()
        )

        for img in images:
            stem = Path(img.file_name or img.file_url or "").stem
            r = ratios.get(stem)

            if r is None:
                unmatched += 1
                unmatched_list.append(f"影像#{img.id} {stem}（无对应视盘掩码）")
                continue
            if r < 0:
                empty += 1
                unmatched_list.append(f"影像#{img.id} {stem}（掩码为空）")
                continue
            if AMBIGUOUS_LOW <= r <= AMBIGUOUS_HIGH:
                ambiguous += 1
                amb_list.append(f"影像#{img.id} {stem} ratio={r:.3f}")
                continue

            eye = disc_right if r > 0.5 else disc_left
            if img.eye != eye:
                if args.apply:
                    img.eye = eye
                updated += 1
            case_eye[img.case_id] = eye

        # 派生对象（mask / overlay / 热力图）继承所属原图的眼别。
        # 它们本就是同一张影像的派生结果，留着 OU 会让安全条在切到
        # 派生图层时又显示回「双眼」，与原图自相矛盾。
        if not args.no_propagate and case_eye:
            derived = (
                session.query(CaseImage)
                .filter(CaseImage.case_table == "training",
                        CaseImage.role != "original",
                        CaseImage.case_id.in_(list(case_eye.keys())))
                .all()
            )
            for d in derived:
                eye = case_eye.get(d.case_id)
                if eye and d.eye != eye:
                    if args.apply:
                        d.eye = eye
                    propagated += 1

        if args.apply:
            session.commit()
    finally:
        session.close()

    print(f"{'已回填' if args.apply else '可回填'}原图　　{updated}")
    print(f"{'已传播' if args.apply else '可传播'}派生对象{propagated}")
    print(f"模糊待人工判定　{ambiguous}")
    print(f"无掩码/未匹配　　{unmatched}")
    print(f"空掩码　　　　　{empty}")

    if amb_list:
        print("-" * 70)
        print(f"模糊带（{AMBIGUOUS_LOW}~{AMBIGUOUS_HIGH}），未自动判定：")
        for x in amb_list:
            print(f"  {x}")

    if unmatched_list:
        print("-" * 70)
        print("未能判定（保持 OU / 原值）：")
        for x in unmatched_list[:20]:
            print(f"  {x}")
        if len(unmatched_list) > 20:
            print(f"  ... 另有 {len(unmatched_list) - 20} 条")

    if not args.apply:
        print("-" * 70)
        print("预演结束，未写库。确认映射无误后加 --apply 执行。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
