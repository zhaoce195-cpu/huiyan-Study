"""
学员开户申请表（与机构加入申请完全分离）
- 未登录访客提交：姓名 / 手机 / 科室 / 理由
- 状态：PENDING / APPROVED / REJECTED
- 通过后生成 STUDENT 账号，并短信 + 站内信告知初密
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class StudentAppStatusEnum(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class StudentApplication(Base, TimestampMixin):
    __tablename__ = "biz_student_application"
    __table_args__ = (
        Index("ix_stu_app_phone_status", "phone", "status"),
        {"comment": "学员开户申请表"},
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, comment="申请ID"
    )
    real_name: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="申请人姓名"
    )
    phone: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True, comment="手机号"
    )
    department: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", comment="所在科室"
    )
    reason: Mapped[str] = mapped_column(
        String(500), nullable=False, default="", comment="申请理由"
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=StudentAppStatusEnum.PENDING.value,
        index=True, comment="PENDING / APPROVED / REJECTED",
    )

    reviewer_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("sys_user.id", ondelete="SET NULL"),
        nullable=True, comment="审核人",
    )
    review_comment: Mapped[str] = mapped_column(
        String(500), nullable=False, default="", comment="审核意见 / 驳回理由"
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="审核时间"
    )
    created_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("sys_user.id", ondelete="SET NULL"),
        nullable=True, comment="通过后生成的学员账号",
    )
    notify_sms: Mapped[str] = mapped_column(
        Text, nullable=False, default="", comment="最近一次短信正文（审计）"
    )

    reviewer = relationship("User", lazy="joined", foreign_keys=[reviewer_id])
    created_user = relationship("User", lazy="joined", foreign_keys=[created_user_id])

    def __repr__(self) -> str:
        return f"<StudentApplication #{self.id} {self.phone} {self.status}>"
