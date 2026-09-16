"""
管理员 · 用户账号
- 列表 / 新建（STUDENT / TEACHER / ADMIN）
- 重置密码（生成临时密码，下次登录必改）
- 停用 / 启用（停用后不能登录）
"""

import secrets
import string
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.models import Role, User
from app.db.models.user import RoleEnum, UserTypeEnum
from app.schemas.user import (
    AdminResetPasswordOut,
    AdminSetActiveParams,
    AdminUserCreate,
    AdminUserItem,
    AdminUserPage,
)
from app.services.op_log_service import OpLogService

_MANAGEABLE = {
    RoleEnum.STUDENT.value,
    RoleEnum.TEACHER.value,
    RoleEnum.ADMIN.value,
}

_ROLE_TO_TYPE = {
    RoleEnum.STUDENT.value: UserTypeEnum.STUDENT.value,
    RoleEnum.TEACHER.value: UserTypeEnum.TEACHER.value,
    RoleEnum.ADMIN.value: UserTypeEnum.ADMIN.value,
}


def _to_item(user: User) -> AdminUserItem:
    return AdminUserItem(
        id=user.id,
        username=user.username,
        real_name=user.real_name or "",
        role=user.role.code if user.role else "",
        role_name=user.role.name if user.role else "",
        department=user.department or "",
        is_active=bool(user.is_active),
        must_change_password=bool(getattr(user, "must_change_password", False)),
        last_login_at=user.last_login_at,
        created_at=user.created_at,
    )


def _temp_password() -> str:
    """字母 + 数字，满足登录改密强度（至少 6 位且非纯字母/纯数字）。"""
    alphabet = string.ascii_letters + string.digits
    body = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        *(secrets.choice(alphabet) for _ in range(5)),
    ]
    secrets.SystemRandom().shuffle(body)
    return "Hy" + "".join(body)


def _get_role(db: Session, code: str) -> Role:
    role = db.query(Role).filter(Role.code == code).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"角色不存在：{code}",
        )
    return role


def _get_user(db: Session, user_id: int) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"账号不存在：{user_id}",
        )
    return user


def _active_admin_count(db: Session, exclude_id: Optional[int] = None) -> int:
    q = (
        db.query(func.count(User.id))
        .join(Role, Role.id == User.role_id)
        .filter(
            Role.code == RoleEnum.ADMIN.value,
            User.is_active == True,  # noqa: E712
        )
    )
    if exclude_id is not None:
        q = q.filter(User.id != exclude_id)
    return int(q.scalar() or 0)


class AdminUserService:

    @staticmethod
    def list_users(
        db: Session,
        *,
        keyword: Optional[str] = None,
        role: Optional[str] = None,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> AdminUserPage:
        q = (
            db.query(User)
            .join(Role, Role.id == User.role_id)
            .filter(Role.code.in_(_MANAGEABLE))
        )
        if keyword:
            kw = f"%{keyword.strip()}%"
            q = q.filter(or_(
                User.username.like(kw),
                User.real_name.like(kw),
                User.department.like(kw),
            ))
        if role:
            if role not in _MANAGEABLE:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="角色筛选只能是 STUDENT / TEACHER / ADMIN",
                )
            q = q.filter(Role.code == role)
        if is_active is not None:
            q = q.filter(User.is_active == is_active)

        total = q.count()
        rows = (
            q.order_by(desc(User.id))
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return AdminUserPage(
            total=total,
            page=page,
            page_size=page_size,
            list=[_to_item(u) for u in rows],
        )

    @staticmethod
    def create_user(
        db: Session,
        *,
        operator: User,
        params: AdminUserCreate,
        ip: str = "",
    ) -> AdminUserItem:
        role_code = params.role.value if isinstance(params.role, RoleEnum) else str(params.role)
        if role_code not in _MANAGEABLE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="角色只能是 STUDENT / TEACHER / ADMIN",
            )
        exists = db.query(User).filter(User.username == params.username).first()
        if exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"账号已存在：{params.username}",
            )
        role = _get_role(db, role_code)
        user = User(
            username=params.username,
            password_hash=hash_password(params.password),
            real_name=params.real_name.strip(),
            department=(params.department or "").strip(),
            role_id=role.id,
            user_type=_ROLE_TO_TYPE[role_code],
            is_active=True,
            must_change_password=True,
        )
        db.add(user)
        db.flush()
        OpLogService.record(
            db, user=operator, module="user", action="create_account",
            detail=f"新建账号 {user.username}（{role_code}）",
            ip=ip, commit=False,
        )
        db.commit()
        db.refresh(user)
        return _to_item(user)

    @staticmethod
    def reset_password(
        db: Session,
        *,
        operator: User,
        user_id: int,
        ip: str = "",
    ) -> AdminResetPasswordOut:
        user = _get_user(db, user_id)
        temp = _temp_password()
        user.password_hash = hash_password(temp)
        user.must_change_password = True
        OpLogService.record(
            db, user=operator, module="user", action="reset_password",
            detail=f"重置账号 {user.username} 的密码",
            ip=ip, commit=False,
        )
        db.commit()
        return AdminResetPasswordOut(
            user_id=user.id,
            username=user.username,
            temp_password=temp,
            must_change_password=True,
        )

    @staticmethod
    def set_active(
        db: Session,
        *,
        operator: User,
        user_id: int,
        params: AdminSetActiveParams,
        ip: str = "",
    ) -> AdminUserItem:
        user = _get_user(db, user_id)
        if user.id == operator.id and not params.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不能停用当前登录账号",
            )
        role_code = user.role.code if user.role else ""
        if (
            not params.is_active
            and role_code == RoleEnum.ADMIN.value
            and _active_admin_count(db, exclude_id=user.id) == 0
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="至少保留一名启用中的管理员",
            )
        user.is_active = bool(params.is_active)
        verb = "启用" if params.is_active else "停用"
        OpLogService.record(
            db, user=operator, module="user", action="set_active",
            detail=f"{verb}账号 {user.username}",
            ip=ip, commit=False,
        )
        db.commit()
        db.refresh(user)
        return _to_item(user)
