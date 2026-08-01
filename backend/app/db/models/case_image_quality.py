"""
影像质量评估结果表

对应《医学培训端评估与工作流重构报告》P0/P1：
    「缺图像质量入口：低质量图可能被当正常或被强制作答」
    「先质量后诊断：图像未加载、眼别冲突或质量不可判读时，不能默认为正常」

设计要点：
    1. 质量结果是「派生对象」，与原始影像记录解耦，单独建表而不是往 CaseImage 加列；
    2. 记录模型名与评估时间，便于换模型后重算与追溯；
    3. 每张影像仅保留最新一条结果（case_image_id 唯一），重评时覆盖。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


# 质量等级取值见 app.common.image_safety.QUALITY_TEXT
# （good / usable / poor / ungradable / unknown）


class CaseImageQuality(Base, TimestampMixin):
    __tablename__ = "biz_case_image_quality"
    __table_args__ = {"comment": "影像质量评估结果（派生对象）"}

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, comment="主键ID"
    )
    case_image_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("biz_case_image.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
        comment="对应影像ID（每张影像仅保留最新一条）",
    )

    # good / usable / poor / ungradable
    quality: Mapped[str] = mapped_column(
        String(16), nullable=False, default="unknown",
        comment="质量等级：good/usable/poor/ungradable/unknown",
    )
    confidence: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, comment="最高类别的置信度",
    )
    probabilities: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="各等级概率分布",
    )

    model_name: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", comment="评估所用模型",
    )
    infer_duration_ms: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="推理耗时（毫秒）",
    )
    checked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="评估时间",
    )
    # 算法服务不可用时记录原因，界面据此显示「未评估」而不是伪造合格
    error_msg: Mapped[str] = mapped_column(
        String(255), nullable=False, default="", comment="评估失败原因（成功时为空）",
    )

    image = relationship("CaseImage", foreign_keys=[case_image_id], lazy="joined")
