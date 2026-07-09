"""
教学实训分享记录表
- 医生临时分享病例给学员实训演示
- 医生提交病例入库申请（管理员审核）
- 脱敏快照存储，原始病例数据零修改
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class ShareTypeEnum(str, Enum):
    TEMPORARY = "TEMPORARY"
    PERMANENT = "PERMANENT"


class ShareSourceEnum(str, Enum):
    SCREENING = "SCREENING"
    TRAINING = "TRAINING"


class ShareStatusEnum(str, Enum):
    SHARING = "SHARING"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SHELVED = "SHELVED"


class TeachingShare(Base, TimestampMixin):
    __tablename__ = "biz_teaching_share"
    __table_args__ = {"comment": "教学实训分享记录表"}

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, comment="分享记录ID"
    )

    share_type: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="分享类型：TEMPORARY/PERMANENT"
    )
    source_type: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="来源类型：SCREENING/TRAINING"
    )
    source_case_id: Mapped[int] = mapped_column(
        Integer, nullable=False, index=True, comment="来源病例ID"
    )
    teaching_case_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("biz_training_case.id", ondelete="SET NULL"),
        nullable=True, comment="入库后关联的教学病例ID"
    )

    desensitized_data: Mapped[dict] = mapped_column(
        JSON, nullable=False, comment="脱敏快照数据"
    )

    share_scope: Mapped[str] = mapped_column(
        String(16), nullable=False, default="ALL", comment="分享范围：ALL/CLASS"
    )
    expire_hours: Mapped[int] = mapped_column(
        Integer, nullable=False, default=24, comment="有效期（小时）"
    )
    expired_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, index=True, comment="过期时间"
    )

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ShareStatusEnum.SHARING.value,
        index=True, comment="状态"
    )

    reviewer_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("sys_user.id", ondelete="SET NULL"),
        nullable=True, comment="审核人ID"
    )
    review_comment: Mapped[str] = mapped_column(
        String(500), nullable=False, default="", comment="审核备注"
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="审核时间"
    )

    teacher_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sys_user.id", ondelete="RESTRICT"),
        nullable=False, index=True, comment="分享教师ID"
    )

    teacher = relationship("User", foreign_keys=[teacher_id], lazy="joined")
    reviewer = relationship("User", foreign_keys=[reviewer_id], lazy="joined")
    teaching_case = relationship("TrainingCase", foreign_keys=[teaching_case_id], lazy="joined")

    def __repr__(self) -> str:
        return f"<TeachingShare #{self.id} {self.share_type} {self.status}>"
