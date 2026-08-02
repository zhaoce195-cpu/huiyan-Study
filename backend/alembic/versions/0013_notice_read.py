"""persist notice read state

Revision ID: 0013_notice_read
Revises: 0012_score_rule_version
Create Date: 2026-08-02 00:00:00

已读状态原本存在进程内存的字典里（notice_service._read_set）：
    · 后端一重启，所有人的已读全部丢失，消息又变回未读；
    · 多副本部署时每个进程各存一份，同一个用户刷新两次看到的状态不同。

对「收件箱」这种功能来说这不是性能取舍，而是功能本身不成立 ——
标记已读的唯一意义就是它下次还在。

存量已读状态无法迁移（它从来就没落过盘），升级后所有消息回到未读一次。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0013_notice_read"
down_revision: Union[str, None] = "0012_score_rule_version"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "biz_notice_read",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("notice_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["sys_user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["notice_id"], ["biz_notice.id"], ondelete="CASCADE"),
        comment="公告已读记录",
    )
    op.create_index("ix_biz_notice_read_user_id", "biz_notice_read", ["user_id"])
    op.create_index("ix_biz_notice_read_notice_id", "biz_notice_read", ["notice_id"])
    # 唯一约束是防重的实质保障：先查后插在并发下会漏
    op.create_index(
        "ux_notice_read_user_notice", "biz_notice_read",
        ["user_id", "notice_id"], unique=True,
    )


def downgrade() -> None:
    op.drop_table("biz_notice_read")
