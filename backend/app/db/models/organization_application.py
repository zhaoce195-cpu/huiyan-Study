"""
机构加入申请表
- 普通用户（PATIENT）提交申请，状态：PENDING / APPROVED / REJECTED
- 管理员审核后写入 reviewer / review_comment / reviewed_at
- 审核动作通过 OrganizationService.review() 触发，并自动 push UserMessage
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class AppStatusEnum(str, Enum):
    """申请状态"""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class OrganizationApplication(Base, TimestampMixin):
    __tablename__ = "biz_organization_application"
    __table_args__ = (
        Index("ix_org_app_applicant_status", "applicant_id", "status"),
        Index("ix_org_app_org_status", "organization_id", "status"),
        {"comment": "机构加入申请表"},
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, comment="申请ID"
    )
    applicant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sys_user.id", ondelete="CASCADE"),
        nullable=False, comment="申请人用户ID",
    )
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("biz_organization.id", ondelete="RESTRICT"),
        nullable=False, comment="目标机构ID",
    )
    reason: Mapped[str] = mapped_column(
        String(500), nullable=False, default="", comment="申请理由"
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=AppStatusEnum.PENDING.value,
        index=True, comment="状态：PENDING/APPROVED/REJECTED",
    )

    reviewer_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("sys_user.id", ondelete="SET NULL"),
        nullable=True, comment="审核人用户ID",
    )
    review_comment: Mapped[str] = mapped_column(
        String(500), nullable=False, default="", comment="审核意见 / 驳回理由"
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="审核时间"
    )

    applicant = relationship("User", lazy="joined", foreign_keys=[applicant_id])
    reviewer = relationship("User", lazy="joined", foreign_keys=[reviewer_id])
    organization = relationship("Organization", lazy="joined")

    def __repr__(self) -> str:
        return f"<OrganizationApplication #{self.id} user={self.applicant_id} org={self.organization_id} {self.status}>"
