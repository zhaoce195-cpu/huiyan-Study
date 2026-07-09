"""
SQLAlchemy 声明式基类
所有 ORM 模型继承 Base，alembic 迁移时通过 Base.metadata 收集所有表
"""

from datetime import datetime
from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """所有模型基类"""
    pass


class TimestampMixin:
    """通用时间戳字段（创建时间 / 更新时间）"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
        comment="创建时间",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="更新时间",
    )
