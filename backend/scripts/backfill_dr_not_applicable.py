# -*- coding: utf-8 -*-
"""
存量回填：把被误标为「0 级无 DR」的非 DR 病例改为「不适用」

对应《医学培训端评估与工作流重构报告》P1：
    「非 DR 病例仍显示『0 级无 DR』，把『不适用』误表达为『0 级』。」

回填规则（两个条件必须同时满足，避免误伤真实分级）：
    1. 病种属于不做 DR 分级的类别：AMD / GLAUCOMA / HYPERTENSION / OTHER
       —— DR 病例本就要分级；NORMAL（正常眼底）的「0 级无 DR」是有意义的结论，
          两者都不动；
    2. 当前 gold_dr_grade 恰为默认值 '0'
       —— 若为 1~4，说明有人确实对该病例做过分级，保留。

用法：
    # 预演（默认，不写库）
    python scripts/backfill_dr_not_applicable.py

    # 实际写入
    python scripts/backfill_dr_not_applicable.py --apply

    # 指定数据库（默认取 app.core.config 的配置）
    python scripts/backfill_dr_not_applicable.py --apply --db sqlite:///edu_eye.db
"""

import argparse
import sys
from pathlib import Path

# Windows 控制台默认 GBK，输出特殊字符会抛 UnicodeEncodeError，
# 若发生在 commit 之后会被 except 捕获并打印出误导性的「已回滚」。
# 这里统一改为 UTF-8 且遇到不可编码字符时替换，不让打印影响事务判定。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 允许以 `python scripts/xxx.py` 直接运行
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.common.dr_grade import (  # noqa: E402
    NON_DR_CATEGORIES,
    should_be_not_applicable,
)
from app.db.models import TrainingCase  # noqa: E402


def build_session(db_url: str):
    engine = create_engine(db_url, future=True)
    return sessionmaker(bind=engine, autoflush=False, future=True)()


def resolve_db_url(explicit: str = "") -> str:
    if explicit:
        return explicit
    try:
        from app.core.config import settings
        url = getattr(settings, "DATABASE_URL", "") or getattr(settings, "SQLALCHEMY_DATABASE_URI", "")
        if url:
            return str(url)
    except Exception:
        pass
    # 兜底：仓库默认的 SQLite
    default_path = Path(__file__).resolve().parent.parent / "edu_eye.db"
    return f"sqlite:///{default_path.as_posix()}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="把非 DR 病种中被误标为 0 级的病例回填为「DR 分级不适用」",
    )
    parser.add_argument("--apply", action="store_true",
                        help="实际写入数据库；不加则仅预演")
    parser.add_argument("--db", default="", help="数据库连接串（可选）")
    args = parser.parse_args()

    db_url = resolve_db_url(args.db)
    print(f"数据库：{db_url}")
    print(f"模式　：{'实际写入' if args.apply else '预演（不写库）'}")
    print(f"规则　：病种 ∈ {sorted(NON_DR_CATEGORIES)} 且 gold_dr_grade == '0'")
    print("-" * 66)

    session = build_session(db_url)
    committed = False
    try:
        cases = session.query(TrainingCase).all()

        targets = [c for c in cases
                   if should_be_not_applicable(c.category, c.gold_dr_grade)]

        # 分类统计，便于人工核对回填范围是否符合预期
        stats = {}
        for c in cases:
            key = (c.category or "?", (c.gold_dr_grade or "").strip() or "(空=不适用)")
            stats[key] = stats.get(key, 0) + 1

        print("当前分布：")
        for (cat, grade), n in sorted(stats.items()):
            mark = "  ← 待回填" if (cat in NON_DR_CATEGORIES and grade == "0") else ""
            print(f"  {cat:<14} {grade:<14} {n:>4} 例{mark}")
        print("-" * 66)

        if not targets:
            print("没有需要回填的病例。")
            return 0

        print(f"待回填 {len(targets)} 例：")
        for c in targets:
            print(f"  #{c.id:<5} {c.case_no:<24} {c.category:<10} "
                  f"'0' → '' （不适用）　{(c.title or '')[:28]}")

        if not args.apply:
            print("-" * 66)
            print("预演结束，未写入。确认无误后加 --apply 执行。")
            return 0

        for c in targets:
            c.gold_dr_grade = ""
        session.commit()
        committed = True
        print("-" * 66)
        print(f"已回填 {len(targets)} 例。")
    except Exception as exc:
        if not committed:
            session.rollback()
            print(f"回填失败，已回滚：{exc}", file=sys.stderr)
            return 1
        # 提交之后再出错（多半是打印/复核环节），数据已落库，不能报「已回滚」
        print(f"回填已提交，但后续步骤出错：{exc}", file=sys.stderr)
        return 0
    finally:
        session.close()

    # 提交后复核（独立于事务，出错不影响已落库的结果）
    try:
        session2 = build_session(db_url)
        remain = [c for c in session2.query(TrainingCase).all()
                  if should_be_not_applicable(c.category, c.gold_dr_grade)]
        session2.close()
        status = "OK" if not remain else "仍有残留，请检查"
        print(f"复核：仍符合回填条件的病例 {len(remain)} 例　{status}")
    except Exception as exc:
        print(f"复核步骤失败（不影响已回填的数据）：{exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
