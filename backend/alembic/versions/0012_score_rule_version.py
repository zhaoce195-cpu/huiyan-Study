"""record which annotation-scoring rule produced each score

Revision ID: 0012_score_rule_version
Revises: 0011_missing_indexes
Create Date: 2026-08-02 00:00:00

对应遗留清单 D-002。

标注分公式为 accuracy*70 + iou_avg*30。当病例没有任何金标准标注框时，
IoU 这一项什么也没度量，却仍占 30% 权重 —— 学员完全答对，标注分也只有
70，总分被压到 85。全库 88 例里有 82 例没有标注框，这不是边角情况。

修正后（版本 2）：无框可比时把 IoU 的权重并回召回率。

历史记录保留版本 1 的分数，不重算 —— 重算会让学员的成绩单在他毫不
知情的情况下变动。版本号让两批分数可区分、可解释。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0012_score_rule_version"
down_revision: Union[str, None] = "0011_missing_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "biz_practice_session",
        sa.Column("score_rule_version", sa.Integer(), nullable=False,
                  server_default="1",
                  comment="标注分算法版本：1 原公式 / 2 修正无框可比时的权重"),
    )
    # 存量记录一律标为版本 1：它们确实是按旧公式算出来的。
    # 不去猜「如果按新规则会是多少」——那既不是学员当时看到的分数，
    # 也不是任何人认可过的成绩。


def downgrade() -> None:
    op.drop_column("biz_practice_session", "score_rule_version")
