"""add biz_case_image_quality table

Revision ID: 0005_case_image_quality
Revises: 0004_teaching_share
Create Date: 2026-08-01 00:00:00

新增表（仅追加，不动任何已有表）：
    biz_case_image_quality

用途：影像质量评估结果（派生对象），支撑「先质量后诊断」门控。
质量结果与原始影像记录解耦，便于换模型后重算与追溯。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0005_case_image_quality"
down_revision: Union[str, None] = "0004_teaching_share"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "biz_case_image_quality",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column(
            "case_image_id", sa.Integer(), nullable=False,
            comment="对应影像ID（每张影像仅保留最新一条）",
        ),
        sa.Column(
            "quality", sa.String(length=16), nullable=False, server_default="unknown",
            comment="质量等级：good/usable/poor/ungradable/unknown",
        ),
        sa.Column(
            "confidence", sa.Float(), nullable=False, server_default="0",
            comment="最高类别的置信度",
        ),
        sa.Column("probabilities", sa.JSON(), nullable=True, comment="各等级概率分布"),
        sa.Column(
            "model_name", sa.String(length=64), nullable=False, server_default="",
            comment="评估所用模型",
        ),
        sa.Column(
            "infer_duration_ms", sa.Integer(), nullable=False, server_default="0",
            comment="推理耗时（毫秒）",
        ),
        sa.Column("checked_at", sa.DateTime(), nullable=True, comment="评估时间"),
        sa.Column(
            "error_msg", sa.String(length=255), nullable=False, server_default="",
            comment="评估失败原因（成功时为空）",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["case_image_id"], ["biz_case_image.id"], ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="影像质量评估结果（派生对象）",
    )
    op.create_index(
        "ix_biz_case_image_quality_case_image_id",
        "biz_case_image_quality",
        ["case_image_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_biz_case_image_quality_case_image_id",
        table_name="biz_case_image_quality",
    )
    op.drop_table("biz_case_image_quality")
