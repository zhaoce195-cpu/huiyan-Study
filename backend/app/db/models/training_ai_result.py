"""
实训病例 AI 诊断结果缓存表
- 存放 CSU-EYES / DRGCNN 对实训病例（TrainingCase）的真实推理结果
- 每个病例缓存一条最新结果；重跑（force）时覆盖更新
- 与教学金标准解耦：金标准是"正确答案"，本表是"AI 的答案"，用于教学对比
"""

from typing import Optional

from sqlalchemy import Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class TrainingAiResult(Base, TimestampMixin):
    __tablename__ = "biz_training_ai_result"
    __table_args__ = {"comment": "实训病例 AI 诊断结果缓存"}

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, comment="主键ID"
    )
    case_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("biz_training_case.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True, comment="实训病例ID",
    )

    # 分级结果（'0'~'4'；单眼病例左右一致）
    left_grade: Mapped[str] = mapped_column(
        String(4), nullable=False, default="0", comment="左眼(OS) DR 分级"
    )
    right_grade: Mapped[str] = mapped_column(
        String(4), nullable=False, default="0", comment="右眼(OD) DR 分级"
    )
    overall_grade: Mapped[str] = mapped_column(
        String(4), nullable=False, default="0", comment="综合 DR 分级（取双眼较重）"
    )

    # GradCAM 热力图（落盘后的相对 URL）
    left_heatmap_path: Mapped[str] = mapped_column(
        String(255), nullable=False, default="", comment="左眼热力图URL"
    )
    right_heatmap_path: Mapped[str] = mapped_column(
        String(255), nullable=False, default="", comment="右眼热力图URL"
    )

    model_name: Mapped[str] = mapped_column(
        String(64), nullable=False, default="CSU-EYES DR", comment="模型名称"
    )
    infer_duration_ms: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="推理耗时（毫秒）"
    )
    raw: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="上游原始 JSON（不含 base64 大字段）"
    )
    risk_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, comment="风险回归值（0~4 连续值）"
    )

    case = relationship("TrainingCase", foreign_keys=[case_id], lazy="joined")

    def __repr__(self) -> str:
        return f"<TrainingAiResult case={self.case_id} OS:{self.left_grade} OD:{self.right_grade}>"
