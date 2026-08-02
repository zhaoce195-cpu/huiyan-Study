"""LTI 1.3 platform registration

Revision ID: 0010_lti_platform
Revises: 0009_case_image_dicom_uid
Create Date: 2026-08-02 00:00:00

慧眼作为 LTI Tool 挂进 Moodle 等 LMS。

采用 LTI 1.3 / LTI Advantage 标准而不是自己实现一套对接协议：
不管院方现在有没有 LMS，支持这个标准本身就是国际背书；
换一家 LMS 时也不用重做集成。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0010_lti_platform"
down_revision: Union[str, None] = "0009_case_image_dicom_uid"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "biz_lti_platform",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False, server_default=""),
        sa.Column("issuer", sa.String(255), nullable=False),
        sa.Column("client_id", sa.String(255), nullable=False),
        sa.Column("deployment_id", sa.String(255), nullable=False),
        sa.Column("auth_login_url", sa.String(512), nullable=False, server_default=""),
        sa.Column("auth_token_url", sa.String(512), nullable=False, server_default=""),
        sa.Column("key_set_url", sa.String(512), nullable=False, server_default=""),
        sa.Column("auto_provision", sa.Boolean(), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        comment="LTI 1.3 平台注册表",
    )
    op.create_index("ix_biz_lti_platform_issuer", "biz_lti_platform", ["issuer"])
    # 同一 issuer + client_id 下每次安装是一个 deployment，三元组才唯一
    op.create_index(
        "ux_lti_platform_triple", "biz_lti_platform",
        ["issuer", "client_id", "deployment_id"], unique=True,
    )

    op.create_table(
        "biz_lti_nonce",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nonce", sa.String(128), nullable=False),
        sa.Column("issuer", sa.String(255), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        comment="LTI nonce 防重放",
    )
    # 唯一约束是防重放的实质保障：并发两次提交同一 token 时，
    # 先查后插会有窗口，靠数据库拒绝才可靠
    op.create_index("ux_biz_lti_nonce", "biz_lti_nonce", ["nonce"], unique=True)

    op.create_table(
        "biz_lti_launch",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("platform_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("lti_user_id", sa.String(255), nullable=False, server_default=""),
        sa.Column("context_id", sa.String(255), nullable=False, server_default=""),
        sa.Column("resource_link_id", sa.String(255), nullable=False, server_default=""),
        sa.Column("lineitem_url", sa.String(1024), nullable=False, server_default=""),
        sa.Column("scope", sa.Text(), nullable=False, server_default=""),
        sa.Column("roles", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        comment="LTI 启动上下文",
    )
    op.create_index("ix_biz_lti_launch_platform", "biz_lti_launch", ["platform_id"])
    op.create_index("ix_biz_lti_launch_user", "biz_lti_launch", ["user_id"])


def downgrade() -> None:
    op.drop_table("biz_lti_launch")
    op.drop_table("biz_lti_nonce")
    op.drop_table("biz_lti_platform")
