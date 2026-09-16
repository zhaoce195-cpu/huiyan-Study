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
    """
    通用时间戳字段（创建时间 / 更新时间）

    时间戳一律由 Python 侧生成，跟业务字段（各 service 里的 datetime.now()）同源。

    此前用的是 server_default=func.now()：SQLite 的 CURRENT_TIMESTAMP 返回 **UTC**，
    而业务字段是容器本地时区（TZ=Asia/Shanghai）的 CST，同一条记录两套时间源，
    列表里的「创建时间 / 更新时间」就比「发布时间」之类恒少 8 小时。

    server_default 保留：只在绕过 ORM 的裸 SQL 插入时兜底，走 ORM 时永远用不到。
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        server_default=func.now(),
        nullable=False,
        comment="创建时间",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        server_default=func.now(),
        nullable=False,
        comment="更新时间",
    )
