# -*- coding: utf-8 -*-
"""
把一个「早年 create_all 建、从未纳管」的库对齐到当前模型

适用场景：库里有数据、有表，但既没有 alembic_version，结构也落后于模型
好几个版本 —— 生产上第一台机器往往就是这样。

为什么不能直接 stamp + upgrade：
    stamp 到某个版本等于宣称「这一版之前的变更都已生效」。可这类库
    连从来没进过迁移的列都缺（比如 sys_user.wx_openid，它只在开发机
    被 create_all 建出来过）。stamp 完再 upgrade，会在某条迁移给一个
    不存在的列建索引时炸掉，而且是炸在中途 —— 前面的 DDL 已经生效了。

做法：先按模型把缺的表、列、索引补齐，再 stamp head。
全程逐项比对模型，不猜、不硬编码。

    python scripts/reconcile_legacy_db.py            # 只报告
    python scripts/reconcile_legacy_db.py --apply    # 执行
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import create_engine, inspect, text  # noqa: E402
from sqlalchemy.schema import CreateIndex, CreateTable  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.base import Base  # noqa: E402
import app.db.models  # noqa: F401,E402

BACKEND = Path(__file__).resolve().parent.parent


def _add_missing_fks(engine) -> None:
    """
    补模型声明了、库里没有的外键。

    SQLite 不支持 ALTER TABLE ADD CONSTRAINT，只能整表重建。重建有数据的
    表是有风险的动作，所以：只处理确实缺失的，且逐张打印出来。

    留着不补也能跑（SQLite 默认还不强制外键），但 alembic check 会永远
    报漂移 —— 一个永远失败的检查等于没有检查。
    """
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    insp = inspect(engine)
    todo = []
    for name, tbl in Base.metadata.tables.items():
        if name not in insp.get_table_names():
            continue
        have = {
            tuple(f["constrained_columns"])
            for f in insp.get_foreign_keys(name)
        }
        for fk in tbl.foreign_key_constraints:
            cols = tuple(c.name for c in fk.columns)
            if cols not in have:
                el = list(fk.elements)[0]
                todo.append((name, cols, el.column.table.name,
                             el.column.name, fk.ondelete))
    if not todo:
        return

    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        op = Operations(ctx)
        for tname, cols, ref_t, ref_c, ondelete in todo:
            cname = f"fk_{tname}_{cols[0]}"
            try:
                with op.batch_alter_table(tname, recreate="always") as batch:
                    batch.create_foreign_key(
                        cname, ref_t, list(cols), [ref_c], ondelete=ondelete,
                    )
                print(f"✓ 已补外键 {tname}.{cols[0]} → {ref_t}.{ref_c}")
            except Exception as exc:
                print(f"  ! 外键 {cname} 建失败：{str(exc)[:120]}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    engine = create_engine(settings.DATABASE_URL)
    insp = inspect(engine)
    have_tables = set(insp.get_table_names())

    plan_tables, plan_cols, plan_idx = [], [], []

    for name, tbl in Base.metadata.tables.items():
        if name not in have_tables:
            plan_tables.append(name)
            continue
        cols = {c["name"] for c in insp.get_columns(name)}
        for col in tbl.columns:
            if col.name not in cols:
                plan_cols.append((name, col))
        idx_have = {i["name"] for i in insp.get_indexes(name)}
        for ix in tbl.indexes:
            if ix.name not in idx_have:
                plan_idx.append(ix)

    print("=" * 62)
    print(f"目标库：{settings.DATABASE_URL}")
    print(f"缺表 {len(plan_tables)}：{', '.join(plan_tables) or '—'}")
    print(f"缺列 {len(plan_cols)}：")
    for t, c in plan_cols:
        print(f"    {t}.{c.name}  {c.type}")
    print(f"缺索引 {len(plan_idx)}：{', '.join(i.name for i in plan_idx) or '—'}")
    stamped = "alembic_version" in have_tables
    print(f"alembic 纳管：{'是' if stamped else '否'}")

    if not args.apply:
        print("-" * 62)
        print("以上仅为报告。确认无误后加 --apply 执行。")
        print("=" * 62)
        return 0

    dialect = engine.dialect
    with engine.begin() as conn:
        # 1) 缺表：交给 metadata 建，索引会一并带上
        if plan_tables:
            Base.metadata.create_all(
                conn, tables=[Base.metadata.tables[t] for t in plan_tables]
            )
            print(f"✓ 已建表 {len(plan_tables)} 张")

        # 2) 缺列：ADD COLUMN。SQLite 只支持追加列，正好够用。
        #    有非空约束的列必须给默认值，否则已有行填不上。
        for tname, col in plan_cols:
            ddl = f"ALTER TABLE {tname} ADD COLUMN {col.name} " \
                  f"{col.type.compile(dialect)}"
            if not col.nullable:
                default = col.server_default
                if default is not None:
                    ddl += f" NOT NULL DEFAULT {default.arg}"
                elif col.default is not None and getattr(col.default, "arg", None) is not None:
                    val = col.default.arg
                    lit = f"'{val}'" if isinstance(val, str) else str(int(val))
                    ddl += f" NOT NULL DEFAULT {lit}"
                else:
                    # 给不出默认值就保持可空：宁可与模型有一处差异，
                    # 也不要用一个编出来的值填进已有数据
                    print(f"  ! {tname}.{col.name} 非空但无默认值，按可空追加")
            conn.execute(text(ddl))
        if plan_cols:
            print(f"✓ 已补列 {len(plan_cols)} 个")

        # 3) 缺索引
        for ix in plan_idx:
            try:
                conn.execute(CreateIndex(ix))
            except Exception as exc:
                print(f"  ! 索引 {ix.name} 建失败：{str(exc)[:100]}")
        if plan_idx:
            print(f"✓ 已补索引 {len(plan_idx)} 个")

    # 3.5) 缺外键。SQLite 不支持 ADD CONSTRAINT，只能整表重建。
    #      放在最后做：前面的列和索引都补齐了，重建出来的才是完整结构。
    _add_missing_fks(engine)

    # 4) 纳入 alembic 管理
    if not stamped:
        from alembic import command
        from alembic.config import Config

        cfg = Config(str(BACKEND / "alembic.ini"))
        cfg.set_main_option("script_location", str(BACKEND / "alembic"))
        cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
        command.stamp(cfg, "head")
        print("✓ 已 stamp 到 head")

    print("=" * 62)
    engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
