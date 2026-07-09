"""baseline (existing user/role/user_setting tables)

Revision ID: 0001_baseline
Revises:
Create Date: 2026-05-22 00:00:00

说明：
    sys_role / sys_user / sys_user_setting 三张表已通过 init.sql 或
    Base.metadata.create_all() 建立，本基线版本不再重复创建，
    仅将 alembic_version 记录推进到 0001，使后续业务表迁移可叠加。

如果你的数据库尚未建立这三张表，请先执行：
    python init_data.py
"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """空基线：不创建任何表。"""
    pass


def downgrade() -> None:
    """空基线：不删除任何表。"""
    pass
