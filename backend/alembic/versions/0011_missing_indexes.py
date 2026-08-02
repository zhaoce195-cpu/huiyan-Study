"""backfill indexes that only existed in the ORM models

Revision ID: 0011_missing_indexes
Revises: 0010_lti_platform
Create Date: 2026-08-02 00:00:00

对应遗留清单 D-004。

模型上声明了 index=True，但这些索引从未写进迁移。结果是：
    · 新装的库（create_all）有这些索引；
    · 从旧版本升级上来的库没有。
两边结构不一致，而这种差异往往要到「同一个查询在一边快、
在另一边慢得离谱」或唯一约束在一边生效、另一边不生效时才被发现。

其中两个是唯一索引（case_sn），缺了它就挡不住重复业务流水号 ——
这不是性能问题，是数据正确性问题。

外键 biz_screening_case.patient_user_id → sys_user.id 同样只在模型里
声明过。SQLite 加外键需要整表重建，且它默认不强制外键；
放在这里重建一张有数据的表，风险高于收益，故单独留待 MySQL 环境处理，
见文件末尾说明。
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0011_missing_indexes"
down_revision: Union[str, None] = "0010_lti_platform"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (索引名, 表名, 列, 是否唯一)
INDEXES = [
    ("ix_biz_screening_case_case_sn", "biz_screening_case", ["case_sn"], True),
    ("ix_biz_screening_case_patient_phone", "biz_screening_case", ["patient_phone"], False),
    ("ix_biz_screening_case_patient_user_id", "biz_screening_case", ["patient_user_id"], False),
    ("ix_biz_screening_case_report_status", "biz_screening_case", ["report_status"], False),
    ("ix_biz_training_case_archive_status", "biz_training_case", ["archive_status"], False),
    ("ix_biz_training_case_case_sn", "biz_training_case", ["case_sn"], True),
    ("ix_biz_training_case_is_train_case", "biz_training_case", ["is_train_case"], False),
    ("ix_biz_training_case_patient_phone", "biz_training_case", ["patient_phone"], False),
    ("ix_sys_user_phone", "sys_user", ["phone"], False),
    ("ix_sys_user_user_type", "sys_user", ["user_type"], False),
    ("ix_sys_user_wx_openid", "sys_user", ["wx_openid"], False),
]


def _existing(table: str) -> set:
    from sqlalchemy import inspect

    insp = inspect(op.get_bind())
    if table not in insp.get_table_names():
        return set()
    return {i["name"] for i in insp.get_indexes(table)}


def upgrade() -> None:
    # 逐个判断是否已存在：这些索引在「create_all 建的新库」上本就有，
    # 而那类库会被 stamp 到 head 从而跳过本迁移；但手工补过索引的库
    # 也可能已经有了。重复创建会直接失败并中断整条链。
    cache = {}
    for name, table, cols, unique in INDEXES:
        if table not in cache:
            cache[table] = _existing(table)
        if not cache[table]:
            # 表不存在（更早的版本还没建这张表）→ 跳过，
            # 建表时会带上索引
            continue
        if name in cache[table]:
            continue
        op.create_index(name, table, cols, unique=unique)


    _add_patient_user_fk()


def _add_patient_user_fk() -> None:
    """
    补 biz_screening_case.patient_user_id → sys_user.id。

    这个外键同样只在模型里声明过。留着不补，`alembic check` 就会
    永远报漂移 —— 一个永远失败的检查等于没有检查，很快就没人看了。

    SQLite 不支持 ALTER TABLE ADD CONSTRAINT，只能整表重建；
    MySQL 直接加即可。
    """
    from sqlalchemy import inspect

    bind = op.get_bind()
    insp = inspect(bind)
    if "biz_screening_case" not in insp.get_table_names():
        return
    have = {
        tuple(f["constrained_columns"])
        for f in insp.get_foreign_keys("biz_screening_case")
    }
    if ("patient_user_id",) in have:
        return

    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("biz_screening_case", recreate="always") as batch:
            batch.create_foreign_key(
                "fk_screening_case_patient_user", "sys_user",
                ["patient_user_id"], ["id"], ondelete="SET NULL",
            )
    else:
        op.create_foreign_key(
            "fk_screening_case_patient_user", "biz_screening_case", "sys_user",
            ["patient_user_id"], ["id"], ondelete="SET NULL",
        )


def downgrade() -> None:
    for name, table, _cols, _unique in reversed(INDEXES):
        try:
            op.drop_index(name, table_name=table)
        except Exception:
            # 本来就没有的索引，删不掉不算失败
            pass


# ---------------------------------------------------------------------------
# 未在此处理：biz_screening_case.patient_user_id → sys_user.id 外键
#
# SQLite 不支持 ALTER TABLE ADD CONSTRAINT，只能整表重建（batch_alter_table）。
# 而 SQLite 默认 PRAGMA foreign_keys=OFF，加了也不强制 —— 为一个不生效的
# 约束去重建一张有数据的表，风险高于收益。
#
# 生产若使用 MySQL，应单独写一个仅在 mysql 方言下执行的迁移：
#     if op.get_bind().dialect.name == "mysql":
#         op.create_foreign_key(...)
# 在此之前，该字段的引用完整性由应用层保证。
# ---------------------------------------------------------------------------
