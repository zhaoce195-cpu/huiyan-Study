"""add biz_teaching_share table

Revision ID: 0004_teaching_share
Revises: 0003_organization_application_message
Create Date: 2026-05-29 00:00:00

新增表（仅追加，不动任何已有表）：
    biz_teaching_share
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0004_teaching_share"
down_revision: Union[str, None] = "0003_organization_application_message"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _updated_at_default() -> str:
    """
    updated_at 的 server_default，按当前方言取值。

    只有 MySQL 支持 ON UPDATE CURRENT_TIMESTAMP。写死它会让整条迁移链
    在 SQLite 上跑不到底 —— 而迁移链能不能跑到底，正是首次部署时
    才会暴露的问题。
    """
    if op.get_bind().dialect.name == "mysql":
        return "CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
    return "CURRENT_TIMESTAMP"


def upgrade() -> None:
    op.create_table(
        "biz_teaching_share",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="分享记录ID"),
        sa.Column("share_type", sa.String(16), nullable=False, comment="分享类型：TEMPORARY/PERMANENT"),
        sa.Column("source_type", sa.String(16), nullable=False, comment="来源类型：SCREENING/TRAINING"),
        sa.Column("source_case_id", sa.Integer(), nullable=False, comment="来源病例ID"),
        sa.Column("teaching_case_id", sa.Integer(), nullable=True, comment="入库后关联的教学病例ID"),
        sa.Column("desensitized_data", sa.JSON(), nullable=False, comment="脱敏快照数据"),
        sa.Column("share_scope", sa.String(16), nullable=False, server_default="ALL", comment="分享范围"),
        sa.Column("expire_hours", sa.Integer(), nullable=False, server_default="24", comment="有效期（小时）"),
        sa.Column("expired_at", sa.DateTime(), nullable=True, comment="过期时间"),
        sa.Column("status", sa.String(16), nullable=False, server_default="SHARING", comment="状态"),
        sa.Column("reviewer_id", sa.Integer(), nullable=True, comment="审核人ID"),
        sa.Column("review_comment", sa.String(500), nullable=False, server_default="", comment="审核备注"),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True, comment="审核时间"),
        sa.Column("teacher_id", sa.Integer(), nullable=False, comment="分享教师ID"),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        # ON UPDATE CURRENT_TIMESTAMP 是 MySQL 专有语法，SQLite 直接报
        # 「near "ON": syntax error」，整条迁移链在 SQLite 上跑不到底。
        # 按方言取值：MySQL 保持原样（已升级的环境结果不变），
        # 其他方言只给 CURRENT_TIMESTAMP —— 更新时间本来就由
        # TimestampMixin 在 Python 侧维护，不依赖数据库触发。
        sa.Column("updated_at", sa.DateTime(), nullable=True,
                  server_default=sa.text(_updated_at_default()), comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["teaching_case_id"], ["biz_training_case.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["sys_user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["teacher_id"], ["sys_user.id"], ondelete="RESTRICT"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        comment="教学实训分享记录表",
    )
    op.create_index("ix_teaching_share_source", "biz_teaching_share", ["source_type", "source_case_id"])
    op.create_index("ix_teaching_share_teacher_status", "biz_teaching_share", ["teacher_id", "status"])
    op.create_index("ix_teaching_share_type_status", "biz_teaching_share", ["share_type", "status"])
    op.create_index("ix_teaching_share_expired_at", "biz_teaching_share", ["expired_at"])
    op.create_index("ix_teaching_share_status", "biz_teaching_share", ["status"])


def downgrade() -> None:
    op.drop_table("biz_teaching_share")
