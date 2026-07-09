"""
AI 筛查结果表
- 一例 ScreeningCase 可对应多条结果（按眼别 / 模型版本拆分）
- 包含 AI 模型推理：DR 分级、风险评分、热力图、病变标注、医生复核结论
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class EyeSideEnum(str, Enum):
    OD = "OD"  # 右眼
    OS = "OS"  # 左眼
    OU = "OU"  # 双眼汇总


class DrGradeEnum(str, Enum):
    """糖尿病视网膜病变分级（国际临床 5 级）"""
    G0 = "0"  # 无明显视网膜病变
    G1 = "1"  # 轻度非增殖
    G2 = "2"  # 中度非增殖
    G3 = "3"  # 重度非增殖
    G4 = "4"  # 增殖性


class RiskLevelEnum(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class ScreeningResult(Base, TimestampMixin):
    __tablename__ = "biz_screening_result"
    __table_args__ = {"comment": "AI 筛查结果表"}

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, comment="结果ID"
    )

    case_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("biz_screening_case.id", ondelete="CASCADE"),
        nullable=False, index=True, comment="所属筛查病例ID",
    )

    # 眼别
    eye_side: Mapped[str] = mapped_column(
        String(4), nullable=False, default=EyeSideEnum.OU.value,
        comment="眼别：OD右/OS左/OU双",
    )

    # AI 模型
    model_name: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", comment="使用的AI模型名称"
    )
    model_version: Mapped[str] = mapped_column(
        String(32), nullable=False, default="", comment="模型版本号"
    )

    # 关键诊断字段
    dr_grade: Mapped[str] = mapped_column(
        String(4), nullable=False, default=DrGradeEnum.G0.value,
        index=True, comment="DR分级：0~4",
    )
    has_dme: Mapped[bool] = mapped_column(
        Integer, nullable=False, default=0, comment="是否伴有黄斑水肿(DME)：0否 1是"
    )
    risk_level: Mapped[str] = mapped_column(
        String(16), nullable=False, default=RiskLevelEnum.LOW.value,
        index=True, comment="风险等级：LOW/MEDIUM/HIGH/URGENT",
    )
    risk_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, comment="模型综合风险分（0~1）"
    )
    referral_required: Mapped[bool] = mapped_column(
        Integer, nullable=False, default=0,
        comment="是否建议转诊：0否 1是",
    )

    # 病变检出（JSON 数组：[{"type":"MA","count":3,"score":0.92}, ...]）
    lesions: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True,
        comment="病变检出列表：MA微血管瘤/HE硬渗/SE软渗/HM出血等",
    )

    # 病变标注坐标 / 包围盒（JSON 数组）
    annotations: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True,
        comment=(
            "标注几何信息："
            "[{\"type\":\"box\",\"label\":\"MA\",\"x\":120,\"y\":230,\"w\":18,\"h\":18,\"score\":0.92}, ...]"
        ),
    )

    # 热力图与原图缩略
    heatmap_path: Mapped[str] = mapped_column(
        String(255), nullable=False, default="", comment="热力图URL"
    )
    thumbnail_path: Mapped[str] = mapped_column(
        String(255), nullable=False, default="", comment="缩略图URL"
    )

    # AI 推理性能
    infer_duration_ms: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="推理耗时（毫秒）"
    )
    inferred_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="AI推理完成时间"
    )

    # 医生复核
    doctor_diagnosis: Mapped[str] = mapped_column(
        Text, nullable=False, default="", comment="医生最终诊断意见"
    )
    doctor_grade: Mapped[str] = mapped_column(
        String(4), nullable=False, default="", comment="医生定级（覆盖 AI）"
    )
    doctor_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("sys_user.id", ondelete="SET NULL"),
        nullable=True, comment="复核医生ID",
    )
    doctor_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="医生复核时间"
    )

    # 关系
    case = relationship("ScreeningCase", back_populates="results")
    doctor = relationship("User", foreign_keys=[doctor_id], lazy="joined")

    def __repr__(self) -> str:
        return f"<ScreeningResult case={self.case_id} eye={self.eye_side} DR={self.dr_grade}>"
