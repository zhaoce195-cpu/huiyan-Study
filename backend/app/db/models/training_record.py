"""
学员实训记录表

⚠️ 已废弃（2026-08）：这张表**没有任何活跃写入方**，线上是空表。

  仅 training_service 的 submit_annotation / mark_case_done 会写它，而这两个
  端点前端从未调用过。学员的实际提交落在：
      - 自主练习   → PracticeSession（biz_practice_session）
      - 阅片工作台 → ReadingAnnotation（biz_reading_annotation）

  统计口径曾经聚合本表，导致管理端「完成病例 / 学时 / 通过率」恒为 0
  （2026-08 用户测试报告 D-1），现已改为聚合上面两张表。

  新增统计或报表请勿再读本表。表与端点暂时保留，等确认无外部调用方后再清理。

- 一名学员对一份 TrainingCase 的一次提交
- 同一 case + user 可有多条记录（多次练习），通过 attempt_no 区分
- 评分由后端比对学员答案与金标准（IoU、分级一致性等）后写入
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class RecordStatusEnum(str, Enum):
    DRAFT = "DRAFT"            # 进行中（未提交）
    SUBMITTED = "SUBMITTED"    # 已提交待评分
    GRADED = "GRADED"          # 已评分
    REVIEWED = "REVIEWED"      # 教师已点评


class TrainingRecord(Base, TimestampMixin):
    __tablename__ = "biz_training_record"
    __table_args__ = {"comment": "学员实训记录表"}

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, comment="实训记录ID"
    )

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sys_user.id", ondelete="CASCADE"),
        nullable=False, index=True, comment="学员用户ID",
    )
    case_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("biz_training_case.id", ondelete="CASCADE"),
        nullable=False, index=True, comment="实训病例ID",
    )

    attempt_no: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1,
        comment="第几次尝试（同一 case 可练习多次）",
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=RecordStatusEnum.DRAFT.value,
        index=True, comment="状态：DRAFT/SUBMITTED/GRADED/REVIEWED",
    )

    # ============ 学员答卷 ============
    student_dr_grade: Mapped[str] = mapped_column(
        String(4), nullable=False, default="", comment="学员选择的 DR 分级"
    )
    student_diagnosis: Mapped[str] = mapped_column(
        Text, nullable=False, default="", comment="学员书写的诊断结论"
    )
    student_lesions: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True, comment="学员标注的病变列表"
    )
    student_annotations: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True,
        comment=(
            "学员标注几何坐标："
            "[{\"type\":\"box\",\"label\":\"MA\",\"x\":118,\"y\":228,\"w\":20,\"h\":18}, ...]"
        ),
    )

    # ============ 评分结果 ============
    grade_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, comment="分级题得分（0~100）"
    )
    annotation_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, comment="标注题得分（IoU 加权 0~100）"
    )
    diagnosis_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, comment="诊断书写得分（0~100）"
    )
    total_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, index=True,
        comment="总分（0~100）",
    )
    iou_avg: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, comment="标注框平均 IoU"
    )
    is_passed: Mapped[bool] = mapped_column(
        Integer, nullable=False, default=0, comment="是否通过：0否 1是"
    )

    # 用时
    duration_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="作答用时（秒）"
    )

    # 时间节点
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="开始作答时间"
    )
    submitted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="提交时间"
    )
    graded_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="评分完成时间"
    )

    # 教师点评
    teacher_comment: Mapped[str] = mapped_column(
        Text, nullable=False, default="", comment="教师点评内容"
    )
    teacher_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("sys_user.id", ondelete="SET NULL"),
        nullable=True, comment="点评教师ID",
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="教师点评时间"
    )

    # 关系
    user = relationship("User", foreign_keys=[user_id], lazy="joined")
    teacher = relationship("User", foreign_keys=[teacher_id], lazy="joined")
    case = relationship("TrainingCase", back_populates="records")

    def __repr__(self) -> str:
        return f"<TrainingRecord user={self.user_id} case={self.case_id} score={self.total_score}>"
