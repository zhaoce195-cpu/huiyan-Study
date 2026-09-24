"""
用户表模型
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class RoleEnum(str, Enum):
    """角色编码"""
    STUDENT = "STUDENT"
    TEACHER = "TEACHER"
    ADMIN = "ADMIN"
    PATIENT = "PATIENT"


class UserTypeEnum(str, Enum):
    """用户类型（与角色一一对应，方便前端区分医患两侧）"""
    ADMIN = "admin"
    TEACHER = "teacher"
    STUDENT = "student"
    PATIENT = "patient"


class User(Base, TimestampMixin):
    __tablename__ = "sys_user"
    __table_args__ = {"comment": "用户信息表"}

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, comment="用户ID"
    )

    # 登录凭证
    username: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True, comment="登录账号"
    )
    password_hash: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="密码哈希（bcrypt）"
    )

    # 个人资料
    real_name: Mapped[str] = mapped_column(
        String(32), nullable=False, default="", comment="真实姓名"
    )
    phone: Mapped[str] = mapped_column(
        String(20), nullable=False, default="", index=True,
        unique=False,  # 历史数据可能有空字符串重复，通过应用层校验唯一性
        comment="手机号（病患账号必填，唯一）",
    )
    email: Mapped[str] = mapped_column(
        String(128), nullable=False, default="", comment="邮箱"
    )
    department: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", comment="所属科室名称"
    )
    department_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("biz_department.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="所属科室记录。同名科室按医院分开，人员挂在具体这一条上",
    )
    title: Mapped[str] = mapped_column(
        String(32), nullable=False, default="", comment="职称（住院医师/主治医师/副主任医师等）"
    )
    study_year: Mapped[str] = mapped_column(
        String(32), nullable=False, default="", comment="年级，如 2024级"
    )
    rotation_batch: Mapped[str] = mapped_column(
        String(32), nullable=False, default="", comment="轮转批次，如 2026年上半年"
    )
    mentor_group: Mapped[str] = mapped_column(
        String(32), nullable=False, default="", comment="带教组"
    )
    group_editor_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="最近一次修改分组的用户"
    )
    group_edited_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="最近一次修改分组的时间"
    )
    avatar: Mapped[str] = mapped_column(
        String(255), nullable=False, default="", comment="头像URL"
    )

    # 微信小程序 openid（绑定后用于免密登录；空串表示未绑定）
    wx_openid: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", index=True,
        comment="微信小程序 openid",
    )

    user_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default=UserTypeEnum.STUDENT.value,
        index=True,
        comment="用户类型：admin/teacher/student/patient",
    )

    # 角色（外键 + 冗余 code 便于无 join 查询）
    role_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sys_role.id", ondelete="RESTRICT"),
        nullable=False, comment="角色ID"
    )

    # 状态
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="账号是否启用"
    )
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment="下次登录是否必须改密（管理员重置临时密码后置 True）",
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="最近登录时间"
    )
    last_login_ip: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", comment="最近登录IP"
    )

    # 关系
    role = relationship("Role", back_populates="users", lazy="joined")
    home_department = relationship(
        "Department",
        foreign_keys=[department_id],
        lazy="joined",
    )
    setting = relationship(
        "UserSetting",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="joined",
    )

    def __repr__(self) -> str:
        return f"<User #{self.id} {self.username}>"


def actor_role_text(user: Optional["User"]) -> str:
    """界面上区分点按钮的人是教师还是管理员。"""
    code = user.role.code if user is not None and user.role else ""
    return {
        RoleEnum.ADMIN.value: "平台管理员",
        RoleEnum.TEACHER.value: "教师",
        RoleEnum.STUDENT.value: "学员",
    }.get(code, "")
