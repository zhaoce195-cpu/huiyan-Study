"""
考核成绩表
- 学员一次正式考核（多份病例的成绩汇总），与日常练习记录区分
- 题目明细以 JSON 数组保存在 question_records，例如每题对应一个 TrainingRecord 摘要
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class ExamStatusEnum(str, Enum):
    NOT_STARTED = "NOT_STARTED"  # 未开始
    IN_PROGRESS = "IN_PROGRESS"  # 进行中
    SUBMITTED = "SUBMITTED"      # 已提交
    GRADED = "GRADED"            # 已批阅
    EXPIRED = "EXPIRED"          # 已过期


class ExamRecord(Base, TimestampMixin):
    __tablename__ = "biz_exam_record"
    __table_args__ = {"comment": "考核成绩表"}

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, comment="考核记录ID"
    )

    # 考核基本信息
    exam_no: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True,
        comment="考核批次编号：EX2026-S1 等",
    )
    exam_title: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="考核标题"
    )
    exam_round: Mapped[str] = mapped_column(
        String(64), nullable=False, default="",
        comment="考核轮次/期次：2026春季 等",
    )

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sys_user.id", ondelete="CASCADE"),
        nullable=False, index=True, comment="参考学员ID",
    )

    # 题目汇总（每题摘要 JSON：[{"case_id":1,"score":85,"iou":0.8}, ...]）
    question_records: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True, comment="题目明细 JSON 数组"
    )
    total_questions: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="总题数"
    )
    correct_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="完全正确题数"
    )

    # 评分汇总
    total_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, index=True,
        comment="总成绩（百分制）",
    )
    grade_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, comment="分级题汇总得分"
    )
    annotation_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, comment="标注题汇总得分"
    )
    diagnosis_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, comment="诊断题汇总得分"
    )
    pass_score: Mapped[int] = mapped_column(
        Integer, nullable=False, default=60, comment="及格分数线"
    )
    is_passed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="是否合格"
    )
    rank: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="同批次内排名"
    )

    # 状态
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ExamStatusEnum.NOT_STARTED.value,
        index=True, comment="状态：NOT_STARTED/IN_PROGRESS/SUBMITTED/GRADED/EXPIRED",
    )

    # 时间窗口
    duration_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="作答总用时（秒）"
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="开考时间"
    )
    submitted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="交卷时间"
    )
    graded_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="批阅完成时间"
    )

    # 主考与点评
    examiner_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("sys_user.id", ondelete="SET NULL"),
        nullable=True, comment="主考/批阅教师ID",
    )
    teacher_comment: Mapped[str] = mapped_column(
        Text, nullable=False, default="", comment="教师总评"
    )

    # 关系
    user = relationship("User", foreign_keys=[user_id], lazy="joined")
    examiner = relationship("User", foreign_keys=[examiner_id], lazy="joined")

    def __repr__(self) -> str:
        return f"<ExamRecord {self.exam_no} user={self.user_id} score={self.total_score}>"
