"""
实训病例表（带教用例）
- 用于学员阅片练习与考核，与真实临床 ScreeningCase 解耦
- 包含金标准（gold_standard_*）：教学正确答案与参考标注
"""

from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class CaseDifficultyEnum(str, Enum):
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"


class CaseCategoryEnum(str, Enum):
    """病例类别"""
    DR = "DR"            # 糖尿病视网膜病变
    AMD = "AMD"          # 老年性黄斑变性
    GLAUCOMA = "GLAUCOMA"  # 青光眼
    HYPERTENSION = "HYPERTENSION"  # 高血压性视网膜病变
    NORMAL = "NORMAL"    # 正常眼底
    OTHER = "OTHER"


class CaseArchiveStatusEnum(str, Enum):
    """病例归档状态"""
    ACTIVE = "ACTIVE"        # 在用
    ARCHIVED = "ARCHIVED"    # 已归档


class TrainingCase(Base, TimestampMixin):
    __tablename__ = "biz_training_case"
    __table_args__ = {"comment": "实训病例表"}

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, comment="实训病例ID"
    )

    case_no: Mapped[str] = mapped_column(
        String(32), nullable=False, unique=True, index=True,
        comment="实训病例编号：T2026001 等",
    )
    case_sn: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, unique=True, index=True,
        comment="全局唯一业务序列号：CASE+YYYYMMDD+6位随机",
    )
    title: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="病例标题"
    )
    description: Mapped[str] = mapped_column(
        Text, nullable=False, default="", comment="病例描述/教学提示"
    )

    # 分类与难度
    category: Mapped[str] = mapped_column(
        String(16), nullable=False, default=CaseCategoryEnum.DR.value,
        index=True, comment="病例类别：DR/AMD/GLAUCOMA/HYPERTENSION/NORMAL/OTHER",
    )
    difficulty: Mapped[str] = mapped_column(
        String(8), nullable=False, default=CaseDifficultyEnum.EASY.value,
        index=True, comment="难度：EASY/MEDIUM/HARD",
    )

    # 患者脱敏背景
    patient_name: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", comment="患者姓名（脱敏/模拟）"
    )
    patient_age: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="患者年龄（脱敏）"
    )
    patient_gender: Mapped[str] = mapped_column(
        String(2), nullable=False, default="U", comment="患者性别：M/F/U"
    )
    patient_phone: Mapped[str] = mapped_column(
        String(20), nullable=False, default="", index=True,
        comment="患者联系电话（脱敏/模拟）",
    )
    subject_no: Mapped[str] = mapped_column(
        String(32), nullable=False, default="", index=True,
        comment="教学用病人编号。同一编号的多行是同一病人不同时期；空表示没有和其他检查连在一起",
    )
    exam_on: Mapped[str] = mapped_column(
        String(10), nullable=False, default="",
        comment="检查日期 YYYY-MM-DD。数据集没提供就留空，不要编造",
    )
    clinical_info: Mapped[str] = mapped_column(
        Text, nullable=False, default="", comment="临床信息（主诉、病史等）"
    )

    # 影像
    image_paths: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True,
        comment="影像路径 JSON：{\"OD\":[\"...\"],\"OS\":[\"...\"]}",
    )

    # ============ 金标准（教学正确答案） ============
    gold_dr_grade: Mapped[str] = mapped_column(
        String(4), nullable=False, default="0",
        comment="金标准 DR 分级：0~4",
    )
    gold_diagnosis: Mapped[str] = mapped_column(
        Text, nullable=False, default="", comment="金标准诊断结论"
    )
    gold_lesions: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True,
        comment="金标准病变列表：[{\"type\":\"MA\",\"count\":3}, ...]",
    )
    gold_annotations: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True,
        comment=(
            "金标准标注坐标："
            "[{\"type\":\"box\",\"label\":\"MA\",\"x\":120,\"y\":230,\"w\":18,\"h\":18}, ...]"
        ),
    )
    gold_heatmap_path: Mapped[str] = mapped_column(
        String(255), nullable=False, default="", comment="金标准热力图URL"
    )
    teaching_points: Mapped[str] = mapped_column(
        Text, nullable=False, default="",
        comment="教学要点。固定提纲：主要诊断、分级依据、容易漏掉的征象、鉴别诊断、处置思路、相关指南要点",
    )

    # 评分配置
    pass_score: Mapped[int] = mapped_column(
        Integer, nullable=False, default=60, comment="及格分数（百分制）"
    )

    # 发布管理
    is_published: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True,
        comment="是否发布：未发布时学员不可见",
    )
    is_train_case: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True,
        comment="是否已加入实训库：True 后学员端方可见 / 可练习",
    )
    archive_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=CaseArchiveStatusEnum.ACTIVE.value,
        index=True, comment="归档状态：ACTIVE/ARCHIVED",
    )
    creator_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sys_user.id", ondelete="RESTRICT"),
        nullable=False, comment="创建/带教教师ID",
    )

    # 关系
    creator = relationship("User", foreign_keys=[creator_id], lazy="joined")
    records = relationship(
        "TrainingRecord",
        back_populates="case",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<TrainingCase {self.case_no} {self.category}/{self.difficulty}>"
