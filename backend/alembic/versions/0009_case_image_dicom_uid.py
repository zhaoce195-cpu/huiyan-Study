"""persist DICOM instance uids on case image

Revision ID: 0009_case_image_dicom_uid
Revises: 0008_reading_submit_idempotency
Create Date: 2026-08-02 00:00:00

对应遗留清单 D-007。

转换时的 SOP Instance UID 由「病例号 + 本地绝对路径」派生。阅片端要把
界面上的图对应到 PACS 实例，此前只能用同样的输入重算 —— 影像目录搬迁
或换一台机器部署，重算结果就与 PACS 中已有的对不上。

表现是「该病例退回 JPG」：不会配错图，但 DICOM 能力静默失效且无提示，
容易长期不被发现。落库固化之后不再依赖重算。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0009_case_image_dicom_uid"
down_revision: Union[str, None] = "0008_reading_submit_idempotency"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "biz_case_image",
        sa.Column("sop_instance_uid", sa.String(length=72), nullable=True,
                  comment="PACS 中的 SOP Instance UID"),
    )
    op.add_column(
        "biz_case_image",
        sa.Column("series_instance_uid", sa.String(length=72), nullable=True,
                  comment="PACS 中的 Series Instance UID"),
    )
    op.add_column(
        "biz_case_image",
        sa.Column("study_instance_uid", sa.String(length=72), nullable=True,
                  comment="PACS 中的 Study Instance UID"),
    )
    op.create_index(
        "ix_biz_case_image_sop_instance_uid",
        "biz_case_image",
        ["sop_instance_uid"],
    )


def downgrade() -> None:
    op.drop_index("ix_biz_case_image_sop_instance_uid", table_name="biz_case_image")
    op.drop_column("biz_case_image", "study_instance_uid")
    op.drop_column("biz_case_image", "series_instance_uid")
    op.drop_column("biz_case_image", "sop_instance_uid")
