"""
安全工具模块
- 密码哈希（passlib + bcrypt）
- JWT 令牌签发 / 解析
- 服务器端 token 黑名单（用于"登出令牌失效"）
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt
from passlib.context import CryptContext

from app.core.config import settings

# ---------- 密码工具 ----------
# bcrypt 行业标准方案，自带盐值，无需额外维护
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """密码哈希（注册 / 修改密码时使用）"""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """校验明文密码与库中哈希值是否一致"""
    if not plain_password or not hashed_password:
        return False
    return pwd_context.verify(plain_password, hashed_password)


# ---------- JWT 工具 ----------

def create_access_token(
    subject: str | int,
    extra: Optional[dict] = None,
    expires_minutes: Optional[int] = None,
) -> tuple[str, datetime]:
    """
    签发访问令牌

    :param subject: 通常为 user_id
    :param extra: 额外携带的字段（如 role / username）
    :param expires_minutes: 过期分钟数，缺省使用配置项
    :return: (token, 到期时间)
    """
    expire_min = expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    expire_at = datetime.now(timezone.utc) + timedelta(minutes=expire_min)

    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": datetime.now(timezone.utc),
        "exp": expire_at,
        "type": "access",
    }
    if extra:
        payload.update(extra)

    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, expire_at


def decode_access_token(token: str) -> dict:
    """
    解析 JWT；失败抛 PyJWTError
    上层调用应捕获并转为 401
    """
    payload = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )
    return payload


# ---------- Token 黑名单（登出失效） ----------
# 登出后将剩余有效期内的 token jti 放入黑名单。
# 因为本项目无 Redis，使用进程内集合 + 过期时间清理。
# 多实例部署需替换为 Redis（Set + EX）或数据库表。

_BLACKLIST: dict[str, float] = {}


def revoke_token(token: str) -> None:
    """把令牌加入黑名单，到期时自动清理"""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_exp": False},
        )
        exp_ts = float(payload.get("exp", 0))
    except Exception:
        return
    _BLACKLIST[token] = exp_ts
    _gc_blacklist()


def is_token_revoked(token: str) -> bool:
    """检查令牌是否已被注销"""
    _gc_blacklist()
    return token in _BLACKLIST


def _gc_blacklist() -> None:
    """惰性清理：移除已过期的 token，避免内存泄漏"""
    now = datetime.now(timezone.utc).timestamp()
    expired = [t for t, exp in _BLACKLIST.items() if exp < now]
    for t in expired:
        _BLACKLIST.pop(t, None)
