# -*- coding: utf-8 -*-
"""
全新部署：建库并纳入 alembic 管理

本项目的迁移链是**增量式**的：0001 是空基线，表由 ORM 模型
create_all() 建立，此后每次结构变更写一个迁移。因此存在两条路径，
用错会当场出事：

    全新部署   python scripts/bootstrap_db.py      # 建表 + stamp head
    升级已有库 alembic upgrade head                 # 只跑增量

在空库上直接 `alembic upgrade head` 会失败 —— 0006 要给
biz_reading_annotation 加列，而没有任何迁移创建过这张表。
报错是「no such table」，看不出是路径用错了。

用法：
    python scripts/bootstrap_db.py          # 建库并 stamp
    python scripts/bootstrap_db.py --stamp-only   # 已有表，只补 stamp
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import create_engine, inspect  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.base import Base  # noqa: E402
import app.db.models  # noqa: F401,E402  确保所有模型被加载

BACKEND = Path(__file__).resolve().parent.parent


def stamp_head() -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
    command.stamp(cfg, "head")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stamp-only", action="store_true",
                    help="表已存在，只补 alembic_version")
    args = ap.parse_args()

    engine = create_engine(settings.DATABASE_URL)
    insp = inspect(engine)
    existing = set(insp.get_table_names())

    print("=" * 60)
    print(f"目标库：{settings.DATABASE_URL}")
    print(f"现有表：{len(existing)} 张")

    if args.stamp_only:
        if "alembic_version" in existing:
            print("已在 alembic 管理下，无需重复 stamp")
            return 0
        stamp_head()
        print("✓ 已 stamp 到 head")
        return 0

    business = existing - {"alembic_version"}
    if business:
        # 不在已有数据的库上盲目 create_all：它只补缺表，不会改已有表，
        # 结果是「看起来成功了，但结构其实是半新半旧的」。
        print("✗ 库中已有业务表。全新部署请用空库；")
        print("  若这是已有库，应改用：alembic upgrade head")
        print("  若这是 create_all 建的库但没被 alembic 纳管，用：--stamp-only")
        return 1

    Base.metadata.create_all(engine)
    created = set(inspect(engine).get_table_names())
    print(f"✓ 已建表 {len(created)} 张")

    stamp_head()
    print("✓ 已 stamp 到 head（此后一律走 alembic upgrade head）")
    print("=" * 60)
    engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
