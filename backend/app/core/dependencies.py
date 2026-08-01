"""
全局依赖
- get_db        数据库会话
- get_current_user / require_roles  登录 + 角色校验
- oauth2 scheme 与 Swagger 集成（右上角 Authorize 直接登录）
"""

from typing import Annotated, Iterable, Optional

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token, is_token_revoked
from app.db.models.user import RoleEnum, User
from app.db.session import get_db_session

# Bearer token 方案；auto_error=False 由我们自行抛出统一格式
security_scheme = HTTPBearer(auto_error=False, description="在此输入登录接口返回的 token")


def get_db() -> Iterable[Session]:
    """FastAPI 依赖：单请求级数据库会话"""
    yield from get_db_session()


# ---------- 登录鉴权 ----------

def _raise_401(msg: str = "登录已失效，请重新登录") -> None:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=msg,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    request: Request,
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """
    从 Authorization: Bearer <token> 中解析当前登录用户
    校验失败统一返回 401
    """
    if credentials is None or not credentials.credentials:
        _raise_401("缺少访问令牌")

    token = credentials.credentials  # type: ignore[union-attr]

    if is_token_revoked(token):
        _raise_401("令牌已注销，请重新登录")

    # ========== 迁移期：同时接受自建 JWT 与 Keycloak 令牌 ==========
    # 身份正在从自建 JWT 迁往 Keycloak（方案 Phase 1）。迁移期内两种令牌都要认，
    # 否则切换当天所有在线会话会被一次性踢掉。
    # 判定顺序：先试自建 JWT（存量主力），失败再试 Keycloak。
    # 待前端全量切到 OIDC 后，删掉自建分支即可。
    user = None
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            _raise_401("令牌内容异常")
        user = db.query(User).filter(User.id == int(user_id)).first()
    except jwt.ExpiredSignatureError:
        _raise_401("令牌已过期，请重新登录")
    except jwt.PyJWTError:
        # 不是自建 JWT，尝试按 Keycloak 令牌解析
        from app.services.keycloak_client import resolve_local_user

        user = resolve_local_user(db, token)
        if user is None:
            _raise_401("令牌无效")

    if not user:
        _raise_401("用户不存在")
    if user.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被停用，请联系管理员",
        )

    # 把当前 token 挂到 request.state 上，供 logout 接口使用
    request.state.access_token = token
    return user


def require_roles(*roles: RoleEnum):
    """
    角色权限依赖工厂
    用法：
        @router.get("/xxx", dependencies=[Depends(require_roles(RoleEnum.ADMIN))])
        或
        def handler(user = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.TEACHER))): ...
    """
    allowed_codes = {r.value if isinstance(r, RoleEnum) else r for r in roles}

    def checker(current_user: Annotated[User, Depends(get_current_user)]) -> User:
        user_role_code = current_user.role.code if current_user.role else None
        if user_role_code not in allowed_codes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"当前账号角色无权访问，需要：{','.join(allowed_codes)}",
            )
        return current_user

    return checker


# 常用类型别名，供路由直接 Annotated 使用
CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[Session, Depends(get_db)]
