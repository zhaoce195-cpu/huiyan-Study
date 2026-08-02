"""align notice_read timestamps with the model

Revision ID: 0014_notice_read_timestamps
Revises: 0013_notice_read
Create Date: 2026-08-02 00:00:00

0013 把 created_at / updated_at 写成了可空，而 TimestampMixin 声明的是
非空。漂移检查当场抓到 —— 这正是把「当前库与模型无漂移」加进体检的意义：
不一致会在写下的当天被发现，而不是等某天插入时才报约束冲突。

补一个新迁移改正，而不是回去改 0013：改历史迁移对已经升过级的环境
不起作用。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0014_notice_read_timestamps"
down_revision: Union[str, None] = "0013_notice_read"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite 不支持直接改列的可空性，batch 模式会重建表。
    # 这张表刚建、通常还没有数据，重建代价可以忽略。
    with op.batch_alter_table("biz_notice_read") as batch:
        batch.alter_column("created_at", existing_type=sa.DateTime(),
                           nullable=False, server_default=sa.func.now())
        batch.alter_column("updated_at", existing_type=sa.DateTime(),
                           nullable=False, server_default=sa.func.now())


def downgrade() -> None:
    with op.batch_alter_table("biz_notice_read") as batch:
        batch.alter_column("created_at", existing_type=sa.DateTime(), nullable=True)
        batch.alter_column("updated_at", existing_type=sa.DateTime(), nullable=True)
