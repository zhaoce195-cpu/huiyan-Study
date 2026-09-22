"""
病例影像表（一对多）
- 一个 ScreeningCase / TrainingCase 可关联多张影像
- role 字段标注影像类型（原图 / 病灶 mask / 处理产物）
- case_table + case_id 多态指向，应用层维护一致性
"""

from enum import Enum
from typing import Optional

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class CaseImageRoleEnum(str, Enum):
    ORIGINAL = "original"     # 原始眼底图
    MA = "MA"                 # 微血管瘤
    HE = "HE"                 # 出血
    EX = "EX"                 # 硬性渗出
    SE = "SE"                 # 软性渗出
    OD = "OD"                 # 视盘
    COLOR_MASK = "color_mask" # 彩色多病灶 mask
    OVERLAY = "overlay"       # 叠加金标准热力图
    CLASS_MASK = "class_mask" # 单通道训练 mask
    OTHER = "other"


class CaseImageTableEnum(str, Enum):
    SCREENING = "screening"
    TRAINING = "training"


# IDRiD 视为「影像完整」必备的最小集
REQUIRED_ROLES_IDRID = [
    CaseImageRoleEnum.ORIGINAL.value,
    CaseImageRoleEnum.MA.value,
    CaseImageRoleEnum.HE.value,
    CaseImageRoleEnum.EX.value,
    CaseImageRoleEnum.COLOR_MASK.value,
]


class CaseImage(Base, TimestampMixin):
    __tablename__ = "biz_case_image"
    __table_args__ = (
        Index("ix_case_image_case", "case_table", "case_id"),
        Index("ix_case_image_case_role", "case_table", "case_id", "role"),
        {"comment": "病例影像表（一对多）"},
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )

    case_table: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="所属业务表：screening / training",
    )
    case_id: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="对应主表 id",
    )

    role: Mapped[str] = mapped_column(
        String(16), nullable=False,
        comment="影像角色：original/MA/HE/EX/SE/OD/color_mask/overlay/class_mask/other",
    )
    eye: Mapped[str] = mapped_column(
        String(4), nullable=False, default="UK",
        comment="眼别：OD 右眼 / OS 左眼 / OU 双眼 / UK 未标注。未知不得默认成双眼",
    )

    file_url: Mapped[str] = mapped_column(
        String(512), nullable=False, comment="对外访问 URL",
    )
    file_name: Mapped[str] = mapped_column(
        String(255), nullable=False, default="", comment="原始文件名",
    )
    file_size: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="字节数",
    )
    width: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
    )
    height: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
    )

    # ---- PACS 对应关系 ----
    # 转换时的 SOP Instance UID 由「病例号 + 本地绝对路径」派生，
    # 影像目录搬迁或换机器部署后就重算不出来了，表现为该病例
    # 静默退回 JPG、DICOM 能力无声失效。故落库固化，不再依赖重算。
    sop_instance_uid: Mapped[Optional[str]] = mapped_column(
        String(72), nullable=True, index=True, comment="PACS 中的 SOP Instance UID",
    )
    series_instance_uid: Mapped[Optional[str]] = mapped_column(
        String(72), nullable=True, comment="PACS 中的 Series Instance UID",
    )
    study_instance_uid: Mapped[Optional[str]] = mapped_column(
        String(72), nullable=True, comment="PACS 中的 Study Instance UID",
    )

    uploaded_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("sys_user.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    uploader = relationship("User", foreign_keys=[uploaded_by], lazy="joined")

    def __repr__(self) -> str:
        return (
            f"<CaseImage {self.case_table}#{self.case_id} "
            f"{self.role}/{self.eye}>"
        )
