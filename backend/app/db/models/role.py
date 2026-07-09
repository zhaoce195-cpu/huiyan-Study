"""
角色表模型
精简为三类：STUDENT / TEACHER / ADMIN
"""

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Role(Base, TimestampMixin):
    __tablename__ = "sys_role"
    __table_args__ = {"comment": "角色表"}

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, comment="角色ID"
    )
    code: Mapped[str] = mapped_column(
        String(32), nullable=False, unique=True, index=True, comment="角色编码：STUDENT/TEACHER/ADMIN"
    )
    name: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="角色显示名"
    )
    remark: Mapped[str] = mapped_column(
        String(255), nullable=False, default="", comment="角色描述"
    )

    # 反向关系：一个角色对应多个用户
    users = relationship("User", back_populates="role")

    def __repr__(self) -> str:
        return f"<Role {self.code}:{self.name}>"
