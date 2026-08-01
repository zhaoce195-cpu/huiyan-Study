"""structured diagnosis for reading and practice

Revision ID: 0006_structured_diagnosis
Revises: 0005_case_image_quality
Create Date: 2026-08-01 00:00:00

对应《医学培训端评估与工作流重构报告》P1：
    「阅片提交只有自由备注，结论难评分、难审计、难统计」

新增列（仅追加，不动已有数据）：
    biz_reading_annotation.diagnosis            结构化诊断结论
    biz_practice_session.student_diagnosis_form 结构化诊断作答
    biz_practice_session.scoring_mode           评分口径版本

关于 scoring_mode
    存量记录默认 keyword，即沿用原来的自由文本关键词评分。
    两种口径显式区分而不是悄悄混用——否则历史成绩无法解释、无法对比。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0006_structured_diagnosis"
down_revision: Union[str, None] = "0005_case_image_quality"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "biz_reading_annotation",
        sa.Column("diagnosis", sa.JSON(), nullable=True, comment="结构化诊断结论"),
    )
    op.add_column(
        "biz_practice_session",
        sa.Column("student_diagnosis_form", sa.JSON(), nullable=True,
                  comment="结构化诊断作答"),
    )
    op.add_column(
        "biz_practice_session",
        sa.Column("scoring_mode", sa.String(length=16), nullable=False,
                  server_default="keyword",
                  comment="评分口径：keyword / structured"),
    )


def downgrade() -> None:
    op.drop_column("biz_practice_session", "scoring_mode")
    op.drop_column("biz_practice_session", "student_diagnosis_form")
    op.drop_column("biz_reading_annotation", "diagnosis")
