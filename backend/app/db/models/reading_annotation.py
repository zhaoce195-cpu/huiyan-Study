"""
影像阅片标注表
- 一份"会话级"标注集合：用户在阅片画布上创建的标注集合（盒/折线/距离/角度/笔刷等）
- 与病例 ID、用户 ID 关联
- 与 TrainingRecord 的"提交批改"分开：阅片可以是临床浏览态，不必触发 IoU 评分
"""

from enum import Enum
from typing import Optional

from sqlalchemy import ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class ReadingStatusEnum(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    REVIEWED = "REVIEWED"


class ReadingAnnotation(Base, TimestampMixin):
    """阅片标注集合（一行一份阅片快照）"""

    __tablename__ = "biz_reading_annotation"
    __table_args__ = {"comment": "阅片标注表"}

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, comment="标注集合ID"
    )

    case_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("biz_training_case.id", ondelete="CASCADE"),
        nullable=False, index=True,
        comment="病例ID（biz_training_case.id）",
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("sys_user.id", ondelete="CASCADE"),
        nullable=False, index=True,
        comment="阅片用户ID",
    )

    image_index: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="影像序号（image_paths 平铺后的下标）",
    )
    image_url: Mapped[str] = mapped_column(
        String(512), nullable=False, default="",
        comment="阅片时使用的影像 URL（冗余存档，便于回放）",
    )

    # 视图状态：缩放、平移、窗宽窗位（fundus 一般用作色阶/对比度）
    viewport: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True,
        comment='视口状态 {"scale":1.2,"x":0,"y":0,"ww":255,"wl":127,"invert":false}',
    )

    # 标注内容（JSON 数组）：
    # [{
    #   "id":"a1","tool":"rect|polygon|pen|length|angle",
    #   "points":[{"x":..,"y":..}, ...],
    #   "label":"出血","color":"#f53f3f","layer":"primary",
    #   "remark":""
    # }, ...]
    annotations: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True, comment="标注列表（JSON）",
    )

    # 测量结果（JSON 数组）：长度/角度等
    measurements: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True, comment="测量结果（JSON）",
    )

    # 图层显隐快照
    layers: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True,
        comment='图层开关 {"primary":true,"heatmap":false,"gold":false,"my":true}',
    )

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ReadingStatusEnum.DRAFT.value,
        index=True, comment="状态：DRAFT/SUBMITTED/REVIEWED",
    )

    # 结构化诊断结论（报告 P1：仅自由备注导致结论难评分、难审计、难统计）
    # 按病种表单存 {字段key: 值}；note 退化为补充说明。
    diagnosis: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="结构化诊断结论",
    )

    note: Mapped[str] = mapped_column(
        Text, nullable=False, default="", comment="阅片备注",
    )

    review_comment: Mapped[str] = mapped_column(
        Text, nullable=False, default="", comment="教师审核意见",
    )

    reviewer_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("sys_user.id", ondelete="SET NULL"),
        nullable=True, comment="审核教师ID",
    )

    # 关系
    case = relationship("TrainingCase", foreign_keys=[case_id], lazy="joined")
    user = relationship("User", foreign_keys=[user_id], lazy="joined")
    reviewer = relationship("User", foreign_keys=[reviewer_id], lazy="joined")

    def __repr__(self) -> str:
        return f"<ReadingAnnotation #{self.id} case={self.case_id} user={self.user_id}>"
