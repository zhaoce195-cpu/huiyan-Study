"""
学员自主练习记录表
- 与 TrainingRecord 区分：
    TrainingRecord 偏向"教学正式作业"（IoU/分级/教师批改的多维评分）
    PracticeSession 偏向"自主练习自评"，单条记录即包含完整一次自评流程
- 字段聚焦练习全过程：抽取方式、用时、得分、漏诊/误诊/学员答案
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class PracticeStatusEnum(str, Enum):
    DRAFT = "DRAFT"            # 进行中
    SUBMITTED = "SUBMITTED"    # 已提交（含自评分）
    REVIEWED = "REVIEWED"      # 教师已点评（可选）


class PracticeModeEnum(str, Enum):
    RANDOM = "RANDOM"      # 随机抽取
    SELECTED = "SELECTED"  # 自选病例


class PracticeSession(Base, TimestampMixin):
    """学员自主练习会话"""

    __tablename__ = "biz_practice_session"
    __table_args__ = {"comment": "学员自主练习会话表"}

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, comment="练习会话ID",
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sys_user.id", ondelete="CASCADE"),
        nullable=False, index=True, comment="学员用户ID",
    )
    case_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("biz_training_case.id", ondelete="CASCADE"),
        nullable=False, index=True, comment="病例ID（biz_training_case.id）",
    )
    mode: Mapped[str] = mapped_column(
        String(16), nullable=False, default=PracticeModeEnum.RANDOM.value,
        comment="练习模式：RANDOM/SELECTED",
    )
    # PRACTICE：平时练习，作答中可以逐则看提示。
    # EXAM：正式考试，同一场多题，全部交卷前不下发答案。
    attempt_kind: Mapped[str] = mapped_column(
        String(16), nullable=False, default="PRACTICE",
        comment="PRACTICE 平时练习 / EXAM 正式考试",
    )
    exam_group_id: Mapped[str] = mapped_column(
        String(40), nullable=False, default="",
        comment="同一场考试的分组号，平时练习为空",
    )
    exam_index: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="本场第几题，从 1 起",
    )
    exam_total: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="本场题数",
    )
    hint_step: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="平时练习已打开的提示则数",
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=PracticeStatusEnum.DRAFT.value,
        index=True, comment="状态：DRAFT/SUBMITTED/REVIEWED",
    )

    # 学员答卷
    student_dr_grade: Mapped[str] = mapped_column(
        String(4), nullable=False, default="", comment="学员选择的 DR 分级 0~4",
    )
    student_diagnosis: Mapped[str] = mapped_column(
        Text, nullable=False, default="", comment="学员书写的诊断结论",
    )
    # 结构化作答（与阅片端同一套病种表单）。
    # 旧记录为空，此时仍按自由文本关键词评分，保证历史成绩可比。
    student_diagnosis_form: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="结构化诊断作答",
    )
    # 评分口径版本：keyword=自由文本关键词匹配，structured=结构化比对。
    # 显式记录而不是让两种口径悄悄混在一起——否则历史成绩无法解释。
    scoring_mode: Mapped[str] = mapped_column(
        String(16), nullable=False, default="keyword",
        comment="评分口径：keyword / structured",
    )
    # 标注分算法版本。
    #   1 = 原公式 accuracy*70 + iou*30，无框可比时 IoU 项仍占 30% 权重，
    #       导致无病灶病例上全对也只有 70 分
    #   2 = 无框可比时把 IoU 权重并回召回率
    # 历史记录保留版本 1 的分数，不重算：重算会让学员的成绩单
    # 在他毫不知情的情况下变动。版本号让两批分数可区分、可解释。
    score_rule_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1,
        comment="标注分算法版本：1 原公式 / 2 修正无框可比时的权重",
    )

    # 提交幂等键：客户端一次提交动作生成一个，重试时原样带回。
    # 真正要防的不是「多出一条记录」（状态机已经拦住了），而是
    # 「提交成功但响应丢包 → 学员重试收到报错 → 以为白做了」。
    # 同键重试返回原结果，异键才算重复提交。
    submit_request_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, index=True, comment="提交幂等键",
    )

    student_annotations: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True,
        comment="学员标注列表 [{id,tool,points,label,...}]",
    )
    student_measurements: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True, comment="学员测量列表",
    )
    viewport_snapshot: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="提交时的视口快照",
    )

    # 评分结果（百分制）
    score_total: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, index=True,
        comment="总得分 0~100",
    )
    score_grade: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="分级题得分 0~100",
    )
    score_annotation: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="标注题得分（基于 IoU 加权）0~100",
    )
    score_diagnosis: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="诊断书写得分 0~100",
    )
    score_text: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="文字题得分 0~100，计入总分",
    )
    text_question_ids: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True, comment="本次练习的文字题题号",
    )
    text_answers: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True, comment="文字题作答 [{id, value}]",
    )

    iou_avg: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, comment="平均 IoU 0~1",
    )
    accuracy: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, comment="病灶命中率 0~1",
    )

    missed_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="漏诊数",
    )
    false_positive_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="误诊数",
    )

    grade_match: Mapped[bool] = mapped_column(
        Integer, nullable=False, default=0, comment="DR 分级是否一致：0否1是",
    )

    is_passed: Mapped[bool] = mapped_column(
        Integer, nullable=False, default=0, comment="是否通过：0否1是",
    )

    # 错误点位 / 学习建议（JSON）
    error_points: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True,
        comment="错误点位详情 [{label, type:'missed|fp|low_iou', ...}]",
    )
    suggestion: Mapped[str] = mapped_column(
        Text, nullable=False, default="", comment="系统生成的学习建议",
    )

    # 时间
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="开始时间",
    )
    submitted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="提交时间",
    )
    duration_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="作答用时（秒）",
    )

    # 教师可选点评
    teacher_comment: Mapped[str] = mapped_column(
        Text, nullable=False, default="", comment="教师点评（可选）",
    )
    teacher_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("sys_user.id", ondelete="SET NULL"),
        nullable=True, comment="点评教师ID",
    )

    # 关系
    user = relationship("User", foreign_keys=[user_id], lazy="joined")
    teacher = relationship("User", foreign_keys=[teacher_id], lazy="joined")
    case = relationship("TrainingCase", foreign_keys=[case_id], lazy="joined")

    def __repr__(self) -> str:
        return (
            f"<PracticeSession #{self.id} "
            f"user={self.user_id} case={self.case_id} score={self.score_total}>"
        )
