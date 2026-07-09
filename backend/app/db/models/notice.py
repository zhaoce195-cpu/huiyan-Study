"""
公告表模型
- 系统/科室公告，支持可见角色限定与时间窗口
- publisher_id 关联 sys_user.id（发布者）
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class NoticeTypeEnum(str, Enum):
    """公告分类"""
    SYSTEM = "SYSTEM"        # 系统通知
    TRAINING = "TRAINING"    # 培训通知
    SCREENING = "SCREENING"  # 筛查通知
    EXAM = "EXAM"            # 考核通知


class NoticeStatusEnum(str, Enum):
    DRAFT = "DRAFT"          # 草稿
    PUBLISHED = "PUBLISHED"  # 已发布
    ARCHIVED = "ARCHIVED"    # 已下线


class Notice(Base, TimestampMixin):
    __tablename__ = "biz_notice"
    __table_args__ = {"comment": "公告表"}

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, comment="公告ID"
    )

    # 基本信息
    title: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True, comment="公告标题"
    )
    summary: Mapped[str] = mapped_column(
        String(255), nullable=False, default="", comment="公告摘要"
    )
    content: Mapped[str] = mapped_column(
        Text, nullable=False, comment="公告正文（HTML / Markdown）"
    )
    cover_url: Mapped[str] = mapped_column(
        String(255), nullable=False, default="", comment="封面图URL"
    )

    # 分类与状态
    notice_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default=NoticeTypeEnum.SYSTEM.value,
        index=True, comment="公告分类：SYSTEM/TRAINING/SCREENING/EXAM",
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=NoticeStatusEnum.DRAFT.value,
        index=True, comment="状态：DRAFT/PUBLISHED/ARCHIVED",
    )

    # 可见角色（逗号分隔，如 "STUDENT,TEACHER"；为空表示全员可见）
    visible_roles: Mapped[str] = mapped_column(
        String(64), nullable=False, default="",
        comment="可见角色，逗号分隔；空字符串表示全员可见",
    )

    # 是否置顶
    is_top: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="是否置顶"
    )

    # 发布者
    publisher_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sys_user.id", ondelete="RESTRICT"),
        nullable=False, comment="发布者用户ID",
    )

    # 时间窗口
    publish_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="发布时间"
    )
    expire_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="失效时间"
    )

    # 统计
    view_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="阅读次数"
    )

    # 关系
    publisher = relationship("User", lazy="joined", foreign_keys=[publisher_id])

    def __repr__(self) -> str:
        return f"<Notice #{self.id} {self.title}>"
