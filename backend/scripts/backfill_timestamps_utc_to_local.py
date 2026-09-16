# -*- coding: utf-8 -*-
"""
存量回填：把 created_at / updated_at 从 UTC 平移到本地时区（+8h）

对应 2026-08 用户测试报告 A5：
    「入库申请记录 / 公告列表的创建时间、更新时间比实际操作时间少 8 小时。」

根因：TimestampMixin 原先用 server_default=func.now()，SQLite 的 CURRENT_TIMESTAMP
返回 UTC，而各 service 里的业务时间字段用的是 Python datetime.now()（容器
TZ=Asia/Shanghai 的 CST）。同一条记录两套时间源，恒差 8 小时。

代码侧已改为 Python 侧 default=datetime.now（见 app/db/base.py），新数据不再有问题；
本脚本负责把**改动之前**写入的存量行补齐这 8 小时。

只跑一次！重复执行会把时间继续往后推。脚本会在 _migration_marker 表里记标记，
重复执行时直接拒绝，除非显式加 --force。

用法：
    # 预演（默认，不写库）
    python scripts/backfill_timestamps_utc_to_local.py

    # 实际写入
    python scripts/backfill_timestamps_utc_to_local.py --apply

    # 指定数据库
    python scripts/backfill_timestamps_utc_to_local.py --apply --db sqlite:///edu_eye.db
"""

import argparse
import sys
from pathlib import Path

# Windows 控制台默认 GBK，中文输出会乱码甚至抛 UnicodeEncodeError（同其他回填脚本）
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 允许以 `python scripts/xxx.py` 直接运行
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, inspect, text  # noqa: E402

MARKER = "backfill_timestamps_utc_to_local"
OFFSET_HOURS = 8
COLUMNS = ("created_at", "updated_at")


def _resolve_db_url(explicit: str | None) -> str:
    if explicit:
        return explicit
    from app.core.config import settings

    return settings.DATABASE_URL


def _already_applied(conn) -> bool:
    conn.execute(
        text(
            "CREATE TABLE IF NOT EXISTS _migration_marker ("
            "  name VARCHAR(128) PRIMARY KEY,"
            "  applied_at DATETIME DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
    )
    row = conn.execute(
        text("SELECT 1 FROM _migration_marker WHERE name = :n"), {"n": MARKER}
    ).first()
    return row is not None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真正写库，默认只预演")
    ap.add_argument("--db", default=None, help="数据库 URL，默认取 app.core.config")
    ap.add_argument("--force", action="store_true", help="忽略「已执行」标记，强制再跑")
    args = ap.parse_args()

    engine = create_engine(_resolve_db_url(args.db))
    # 平移用的是 SQLite 的 datetime(col, '+N hours')；MySQL 侧 CURRENT_TIMESTAMP
    # 本就跟随会话时区，没有这个偏差，也没必要跑。
    if engine.dialect.name != "sqlite":
        print(f"[跳过] 当前数据库是 {engine.dialect.name}，只有 SQLite 部署存在这 8 小时偏差。")
        return 0
    inspector = inspect(engine)

    with engine.begin() as conn:
        if _already_applied(conn) and not args.force:
            print(f"[跳过] {MARKER} 已经执行过。重复执行会把时间继续往后推。")
            print("       确实要再跑一次请加 --force。")
            return 0

        total = 0
        for table in inspector.get_table_names():
            if table.startswith("_") or table == "alembic_version":
                continue
            cols = {c["name"] for c in inspector.get_columns(table)}
            targets = [c for c in COLUMNS if c in cols]
            if not targets:
                continue

            n = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0
            if not n:
                continue
            total += n
            print(f"  {table}: {n} 行 · 平移 {', '.join(targets)}")

            if args.apply:
                sets = ", ".join(
                    f"{c} = datetime({c}, '+{OFFSET_HOURS} hours')" for c in targets
                )
                where = " OR ".join(f"{c} IS NOT NULL" for c in targets)
                conn.execute(text(f"UPDATE {table} SET {sets} WHERE {where}"))

        if not args.apply:
            print(f"\n[预演] 共 {total} 行待平移 +{OFFSET_HOURS}h。加 --apply 实际写入。")
        else:
            conn.execute(
                text("INSERT INTO _migration_marker (name) VALUES (:n)"), {"n": MARKER}
            )
            print(f"\n[完成] 共 {total} 行已平移 +{OFFSET_HOURS}h。")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
