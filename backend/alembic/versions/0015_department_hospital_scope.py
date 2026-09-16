"""scope departments to a hospital

Revision ID: 0015_department_hospital_scope
Revises: 0014_notice_read_timestamps
Create Date: 2026-08-25 00:00:00

对应 2026-08 用户测试报告 B2：
    「在 ID 为 2 的医院创建科室，切换到其他医院视角，发现该科室也被创建了，
      所有医院显示的科室列表完全一致。」

biz_department 原本压根没有医院字段，list_departments 收下 hospital_id 后
原样丢回去从不使用 —— 也就是根本没有隔离可言。

这里：
  1. 加 hospital_id（可空）。NULL = 全院通用科室，所有医院都能看到；
     存量科室全部留作 NULL，保持现有行为不变，不猜它们该归谁。
  2. code 从全局唯一改成 (hospital_id, code) 唯一 —— 不同医院都该能有
     自己的「眼科 / OPHTH」。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0015_department_hospital_scope"
down_revision: Union[str, None] = "0014_notice_read_timestamps"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite 改不了既有索引/约束，batch 模式会重建表
    with op.batch_alter_table("biz_department") as batch:
        batch.add_column(
            sa.Column(
                "hospital_id",
                sa.Integer(),
                nullable=True,
                comment="所属医院ID；NULL = 全院通用（不限医院可见）",
            )
        )
        # 原来的 code 唯一索引挡住了「不同医院同名科室」，换成普通索引
        batch.drop_index("ix_biz_department_code")
        batch.create_index("ix_biz_department_code", ["code"], unique=False)
        batch.create_index("ix_biz_department_hospital_id", ["hospital_id"], unique=False)
        batch.create_unique_constraint(
            "uq_department_hospital_code", ["hospital_id", "code"]
        )


def downgrade() -> None:
    with op.batch_alter_table("biz_department") as batch:
        batch.drop_constraint("uq_department_hospital_code", type_="unique")
        batch.drop_index("ix_biz_department_hospital_id")
        batch.drop_index("ix_biz_department_code")
        batch.create_index("ix_biz_department_code", ["code"], unique=True)
        batch.drop_column("hospital_id")
