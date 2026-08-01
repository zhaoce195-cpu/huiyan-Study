"""submit idempotency key for practice session

Revision ID: 0007_submit_idempotency
Revises: 0006_structured_diagnosis
Create Date: 2026-08-02 00:00:00

对应《医学培训端评估与工作流重构报告》8.3 P1 用例：
    「保存时断网并重复点击 → 不丢失、不重复提交」

要防的不是「多出一条记录」——状态机本来就拦住了。要防的是：
提交已成功、成绩已落库，但响应在网络上丢了；学员重试收到
「已提交，无法重复提交」的报错，以为答卷白做了。

同键重试回放原结果，异键才判为重复提交。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0007_submit_idempotency"
down_revision: Union[str, None] = "0006_structured_diagnosis"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "biz_practice_session",
        sa.Column("submit_request_id", sa.String(length=64), nullable=True,
                  comment="提交幂等键"),
    )
    op.create_index(
        "ix_biz_practice_session_submit_request_id",
        "biz_practice_session",
        ["submit_request_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_biz_practice_session_submit_request_id",
        table_name="biz_practice_session",
    )
    op.drop_column("biz_practice_session", "submit_request_id")
