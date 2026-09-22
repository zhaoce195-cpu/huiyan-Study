"""文字题作答记录。和阅片练习分开记，避免一张图的成绩单被填空题改写。"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class TextQuizAttempt(Base, TimestampMixin):
    __tablename__ = "biz_text_quiz_attempt"
    __table_args__ = {"comment": "文字练习题作答"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sys_user.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    question_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    detail: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
