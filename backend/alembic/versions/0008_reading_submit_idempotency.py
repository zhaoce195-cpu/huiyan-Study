"""submit idempotency key for reading annotation

Revision ID: 0008_reading_submit_idempotency
Revises: 0007_submit_idempotency
Create Date: 2026-08-02 00:00:00

阅片端的草稿保存是 upsert（复用同用户+同病例+同影像的最近一条草稿），
本身幂等。但提交会把记录置为 SUBMITTED，此时断网重试就找不到草稿了，
会新建一条并再次提交 —— 同一份阅片凭空变成两条记录。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0008_reading_submit_idempotency"
down_revision: Union[str, None] = "0007_submit_idempotency"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "biz_reading_annotation",
        sa.Column("submit_request_id", sa.String(length=64), nullable=True,
                  comment="提交幂等键"),
    )
    op.create_index(
        "ix_biz_reading_annotation_submit_request_id",
        "biz_reading_annotation",
        ["submit_request_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_biz_reading_annotation_submit_request_id",
        table_name="biz_reading_annotation",
    )
    op.drop_column("biz_reading_annotation", "submit_request_id")
