"""
操作日志表
- 记录关键写操作：用户登录、上传、删除、转诊、提交标注 等
- 通过 services/op_log_service.OpLogService.record() 统一写入
"""

from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class OperationLog(Base, TimestampMixin):
    __tablename__ = "biz_op_log"
    __table_args__ = {"comment": "操作日志表"}

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, comment="日志ID"
    )

    user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("sys_user.id", ondelete="SET NULL"),
        nullable=True, index=True, comment="操作用户ID",
    )
    username: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", comment="操作账号（冗余以备用户被删）"
    )

    module: Mapped[str] = mapped_column(
        String(32), nullable=False, default="", index=True,
        comment="模块：auth/screening/training/user/common ...",
    )
    action: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", index=True,
        comment="动作：login/upload/delete/refer ...",
    )
    detail: Mapped[str] = mapped_column(
        Text, nullable=False, default="", comment="详细描述"
    )
    ip: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", comment="客户端IP"
    )

    user = relationship("User", lazy="joined")

    def __repr__(self) -> str:
        return f"<OpLog #{self.id} {self.username} {self.module}.{self.action}>"
