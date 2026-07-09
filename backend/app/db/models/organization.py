"""
机构（组织）表
- 基础维度：名称 / 编码 / 类别 / 联系信息
- 用于普通用户（PATIENT）发起「申请加入机构」时的可选项
- 与现有 biz_department / hospitals 互不冲突，互不替代
"""

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Organization(Base, TimestampMixin):
    __tablename__ = "biz_organization"
    __table_args__ = {"comment": "机构（组织）表"}

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, comment="机构ID"
    )
    name: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True, index=True, comment="机构名称（唯一）"
    )
    code: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", comment="机构编码"
    )
    category: Mapped[str] = mapped_column(
        String(32), nullable=False, default="", comment="机构类别（医院/体检中心/学校 等）"
    )
    address: Mapped[str] = mapped_column(
        String(255), nullable=False, default="", comment="地址"
    )
    contact: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", comment="联系人"
    )
    phone: Mapped[str] = mapped_column(
        String(32), nullable=False, default="", comment="联系电话"
    )
    description: Mapped[str] = mapped_column(
        Text, nullable=False, default="", comment="机构介绍"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="是否启用"
    )

    def __repr__(self) -> str:
        return f"<Organization #{self.id} {self.name}>"
