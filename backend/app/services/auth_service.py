"""
登录认证业务
所有复杂逻辑放这里，路由层只负责接收 / 转发 / 包装响应
"""

from datetime import datetime
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    revoke_token,
    verify_password,
)
from app.db.models import Role, User, UserSetting
from app.schemas.user import LoginRequest, LoginResponse, UserOut


def _build_user_out(user: User) -> UserOut:
    """ORM → Pydantic 出参，统一组装 role / role_name 字段"""
    return UserOut(
        id=user.id,
        username=user.username,
        real_name=user.real_name,
        phone=user.phone,
        email=user.email,
        department=user.department,
        title=user.title,
        avatar=user.avatar,
        role=user.role.code,
        role_name=user.role.name if user.role else "",
        user_type=user.user_type or "",
        is_active=user.is_active,
        must_change_password=bool(getattr(user, "must_change_password", False)),
        last_login_at=user.last_login_at,
        last_login_ip=user.last_login_ip,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


class AuthService:
    """登录认证业务"""

    @staticmethod
    def login(
        db: Session,
        params: LoginRequest,
        client_ip: str = "",
        password_already_verified: bool = False,
    ) -> LoginResponse:
        """
        :param password_already_verified:
            口令已由外部身份提供者（Keycloak）校验通过。

            迁移期内 Keycloak 是口令权威，本地 bcrypt 哈希不再更新，
            两边必然不一致。此时若仍用本地哈希复核，用户改完密码反而登不进来。
            因此外部校验通过后跳过本地口令校验，但账号状态与角色检查照常执行。
        """
        # 1. 查用户
        user: Optional[User] = (
            db.query(User).filter(User.username == params.username).first()
        )
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="账号或密码错误",
            )

        # 2. 校验密码（已由 Keycloak 校验过则跳过）
        if not password_already_verified:
            if not verify_password(params.password, user.password_hash):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="账号或密码错误",
                )

        # 3. 状态
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="账号已被停用，请联系管理员",
            )

        # 4. 确保角色存在
        role: Optional[Role] = user.role
        if not role:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="账号未关联角色，请联系管理员",
            )

        # 5. 自动初始化用户配置
        if not user.setting:
            user.setting = UserSetting(user_id=user.id)

        # 6. 更新登录信息
        user.last_login_at = datetime.now()
        user.last_login_ip = client_ip[:64]

        db.commit()
        db.refresh(user)

        # 7. 签发 token
        token, expire_at = create_access_token(
            subject=user.id,
            extra={"username": user.username, "role": role.code},
        )

        return LoginResponse(
            token=token,
            token_type="Bearer",
            expires_at=expire_at,
            user_info=_build_user_out(user),
        )

    @staticmethod
    def logout(token: str) -> None:
        """注销：把当前令牌加入黑名单，下次访问立即失效"""
        if token:
            revoke_token(token)
