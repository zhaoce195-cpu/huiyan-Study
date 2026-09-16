"""
科室表模型
- 公共主数据，被用户表 department 字段、病例表 department_id 引用
- 仅维护扁平结构（眼科、内分泌科、信息中心 …），如需树形可后续加 parent_id
"""

from typing import Optional

from sqlalchemy import Boolean, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Department(Base, TimestampMixin):
    __tablename__ = "biz_department"
    __table_args__ = (
        # 编码按医院唯一，而不是全局唯一：不同医院都该能有自己的「眼科 / OPHTH」。
        # hospital_id 为 NULL 的是全院通用科室，SQL 语义下多个 NULL 互不冲突，
        # 重复由 service 层拦。
        UniqueConstraint("hospital_id", "code", name="uq_department_hospital_code"),
        {"comment": "科室表"},
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, comment="科室ID"
    )
    hospital_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, index=True,
        comment="所属医院ID；NULL = 全院通用（不限医院可见）",
    )
    code: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True,
        comment="科室编码：OPHTH / ENDO / INFO 等（同一医院内唯一）",
    )
    name: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="科室名称"
    )
    short_name: Mapped[str] = mapped_column(
        String(32), nullable=False, default="", comment="科室简称"
    )
    leader: Mapped[str] = mapped_column(
        String(32), nullable=False, default="", comment="科室负责人姓名"
    )
    phone: Mapped[str] = mapped_column(
        String(32), nullable=False, default="", comment="联系电话"
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="排序值（升序）"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="是否启用"
    )
    remark: Mapped[str] = mapped_column(
        String(255), nullable=False, default="", comment="备注"
    )

    def __repr__(self) -> str:
        return f"<Department {self.code}:{self.name}>"
