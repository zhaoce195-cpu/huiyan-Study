"""
用户站内消息表（per-user）
- 与 biz_notice（公告广播）完全解耦
- 当前仅由「机构申请审核」流程在审核完成后写入
- 后续如需扩展其他场景（系统提醒等），新增 type 即可
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MessageTypeEnum(str, Enum):
    """消息类型"""
    ORG_APPLICATION = "org_application"
    STUDENT_APPLICATION = "student_application"
    SYSTEM = "system"


class UserMessage(Base):
    """
    per-user 站内消息
    注：刻意不复用 TimestampMixin —— 仅需 created_at；read 状态由 is_read + read_at 描述
    """
    __tablename__ = "biz_user_message"
    __table_args__ = (
        Index("ix_user_msg_user_read", "user_id", "is_read"),
        {"comment": "用户站内消息（per-user 推送）"},
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, comment="消息ID"
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sys_user.id", ondelete="CASCADE"),
        nullable=False, index=True, comment="收件人用户ID",
    )
    type: Mapped[str] = mapped_column(
        String(32), nullable=False, default=MessageTypeEnum.SYSTEM.value,
        index=True, comment="消息类型",
    )
    title: Mapped[str] = mapped_column(
        String(128), nullable=False, default="", comment="标题"
    )
    content: Mapped[str] = mapped_column(
        Text, nullable=False, default="", comment="正文"
    )

    ref_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="", comment="关联业务类型（如 org_application）"
    )
    ref_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="关联业务对象ID"
    )

    is_read: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True, comment="是否已读"
    )
    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="已读时间"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, comment="创建时间"
    )

    user = relationship("User", lazy="joined", foreign_keys=[user_id])

    def __repr__(self) -> str:
        return f"<UserMessage #{self.id} user={self.user_id} {self.type} read={self.is_read}>"
