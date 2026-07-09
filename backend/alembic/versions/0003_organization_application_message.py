"""add organization / organization_application / user_message tables

Revision ID: 0003_organization_application_message
Revises: 0002_business_tables
Create Date: 2026-05-28 00:00:00

新增表（仅追加，不动任何已有表）：
    biz_organization
    biz_organization_application
    biz_user_message
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0003_organization_application_message"
down_revision: Union[str, None] = "0002_business_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============================================================
    # 1. biz_organization
    # ============================================================
    op.create_table(
        "biz_organization",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="机构ID"),
        sa.Column("name", sa.String(length=128), nullable=False, comment="机构名称"),
        sa.Column("code", sa.String(length=64), nullable=False, server_default="", comment="机构编码"),
        sa.Column("category", sa.String(length=32), nullable=False, server_default="", comment="机构类别"),
        sa.Column("address", sa.String(length=255), nullable=False, server_default="", comment="地址"),
        sa.Column("contact", sa.String(length=64), nullable=False, server_default="", comment="联系人"),
        sa.Column("phone", sa.String(length=32), nullable=False, server_default="", comment="联系电话"),
        sa.Column("description", sa.Text(), nullable=False, comment="机构介绍"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1"), comment="是否启用"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uk_organization_name"),
        comment="机构（组织）表",
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_biz_organization_name", "biz_organization", ["name"])

    # ============================================================
    # 2. biz_organization_application
    # ============================================================
    op.create_table(
        "biz_organization_application",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="申请ID"),
        sa.Column("applicant_id", sa.Integer(), nullable=False, comment="申请人用户ID"),
        sa.Column("organization_id", sa.Integer(), nullable=False, comment="目标机构ID"),
        sa.Column("reason", sa.String(length=500), nullable=False, server_default="", comment="申请理由"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="PENDING", comment="申请状态"),
        sa.Column("reviewer_id", sa.Integer(), nullable=True, comment="审核人用户ID"),
        sa.Column("review_comment", sa.String(length=500), nullable=False, server_default="", comment="审核意见"),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True, comment="审核时间"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["applicant_id"], ["sys_user.id"],
            name="fk_org_app_applicant", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["biz_organization.id"],
            name="fk_org_app_org", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_id"], ["sys_user.id"],
            name="fk_org_app_reviewer", ondelete="SET NULL",
        ),
        comment="机构加入申请表",
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_org_app_status", "biz_organization_application", ["status"])
    op.create_index("ix_org_app_applicant_status", "biz_organization_application", ["applicant_id", "status"])
    op.create_index("ix_org_app_org_status", "biz_organization_application", ["organization_id", "status"])

    # ============================================================
    # 3. biz_user_message
    # ============================================================
    op.create_table(
        "biz_user_message",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="消息ID"),
        sa.Column("user_id", sa.Integer(), nullable=False, comment="收件人用户ID"),
        sa.Column("type", sa.String(length=32), nullable=False, server_default="system", comment="消息类型"),
        sa.Column("title", sa.String(length=128), nullable=False, server_default="", comment="标题"),
        sa.Column("content", sa.Text(), nullable=False, comment="正文"),
        sa.Column("ref_type", sa.String(length=32), nullable=False, server_default="", comment="关联业务类型"),
        sa.Column("ref_id", sa.Integer(), nullable=True, comment="关联业务对象ID"),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("0"), comment="是否已读"),
        sa.Column("read_at", sa.DateTime(), nullable=True, comment="已读时间"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["sys_user.id"],
            name="fk_user_msg_user", ondelete="CASCADE",
        ),
        comment="用户站内消息（per-user 推送）",
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_user_msg_user", "biz_user_message", ["user_id"])
    op.create_index("ix_user_msg_type", "biz_user_message", ["type"])
    op.create_index("ix_user_msg_read", "biz_user_message", ["is_read"])
    op.create_index("ix_user_msg_user_read", "biz_user_message", ["user_id", "is_read"])


def downgrade() -> None:
    """按外键依赖反向删除"""
    op.drop_table("biz_user_message")
    op.drop_table("biz_organization_application")
    op.drop_table("biz_organization")
