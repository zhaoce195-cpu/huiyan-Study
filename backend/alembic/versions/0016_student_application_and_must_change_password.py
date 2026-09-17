"""student application table + must_change_password

Revision ID: 0016_student_app_must_pwd
Revises: 0015_department_hospital_scope
Create Date: 2026-09-16 00:00:00

本轮功能新增、且只做追加：
    1. sys_user.must_change_password  — 管理员重置 / 开户后的强制改密标记
    2. biz_student_application        — 学员开户申请（与机构申请分表）

不改任何已有列的类型、默认值或约束。线上若已由 _patch_schema 补过，
本迁移按列/表是否存在跳过，避免重复 ADD / CREATE。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0016_student_app_must_pwd"
down_revision: Union[str, None] = "0015_department_hospital_scope"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    return name in sa.inspect(bind).get_table_names()


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    try:
        cols = sa.inspect(bind).get_columns(table)
    except Exception:
        return False
    return any(c["name"] == column for c in cols)


def upgrade() -> None:
    if _has_table("sys_user") and not _has_column("sys_user", "must_change_password"):
        op.add_column(
            "sys_user",
            sa.Column(
                "must_change_password",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("0"),
                comment="下次登录是否必须改密（管理员重置临时密码后置 True）",
            ),
        )

    if _has_table("biz_student_application"):
        return

    op.create_table(
        "biz_student_application",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="申请ID"),
        sa.Column("real_name", sa.String(length=32), nullable=False, comment="申请人姓名"),
        sa.Column("phone", sa.String(length=20), nullable=False, comment="手机号"),
        sa.Column("department", sa.String(length=64), nullable=False, server_default="", comment="所在科室"),
        sa.Column("reason", sa.String(length=500), nullable=False, server_default="", comment="申请理由"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="PENDING", comment="PENDING / APPROVED / REJECTED"),
        sa.Column("reviewer_id", sa.Integer(), nullable=True, comment="审核人"),
        sa.Column("review_comment", sa.String(length=500), nullable=False, server_default="", comment="审核意见 / 驳回理由"),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True, comment="审核时间"),
        sa.Column("created_user_id", sa.Integer(), nullable=True, comment="通过后生成的学员账号"),
        sa.Column("notify_sms", sa.Text(), nullable=False, server_default="", comment="最近一次短信正文（审计）"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["reviewer_id"], ["sys_user.id"],
            name="fk_stu_app_reviewer", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_user_id"], ["sys_user.id"],
            name="fk_stu_app_created_user", ondelete="SET NULL",
        ),
        comment="学员开户申请表",
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_biz_student_application_phone", "biz_student_application", ["phone"])
    op.create_index("ix_biz_student_application_status", "biz_student_application", ["status"])
    op.create_index("ix_stu_app_phone_status", "biz_student_application", ["phone", "status"])


def downgrade() -> None:
    if _has_table("biz_student_application"):
        op.drop_index("ix_stu_app_phone_status", table_name="biz_student_application")
        op.drop_index("ix_biz_student_application_status", table_name="biz_student_application")
        op.drop_index("ix_biz_student_application_phone", table_name="biz_student_application")
        op.drop_table("biz_student_application")
    if _has_table("sys_user") and _has_column("sys_user", "must_change_password"):
        op.drop_column("sys_user", "must_change_password")
