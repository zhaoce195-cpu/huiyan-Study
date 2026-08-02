# -*- coding: utf-8 -*-
"""
公告已读记录

已读状态原本存在进程内存的字典里（notice_service._read_set）。那样：
    · 后端一重启，所有人的已读全部丢失，消息又变回未读；
    · 多副本部署时每个进程各存一份，同一个用户刷新两次看到的状态不同。

对「收件箱」这种功能来说，这不是性能取舍，而是功能本身不成立 ——
标记已读的唯一意义就是它下次还在。
"""

from sqlalchemy import ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class NoticeRead(Base, TimestampMixin):
    """某用户已读某条公告"""

    __tablename__ = "biz_notice_read"
    __table_args__ = (
        # 同一用户对同一公告只有一条记录；靠唯一约束防重，
        # 而不是先查后插 —— 并发下先查后插会漏
        Index("ux_notice_read_user_notice", "user_id", "notice_id", unique=True),
        {"comment": "公告已读记录"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sys_user.id", ondelete="CASCADE"),
        nullable=False, index=True, comment="用户ID",
    )
    notice_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("biz_notice.id", ondelete="CASCADE"),
        nullable=False, index=True, comment="公告ID",
    )
