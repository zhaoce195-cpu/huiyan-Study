# -*- coding: utf-8 -*-
"""
Keycloak 客户端：令牌校验与本地用户解析

对应方案 Phase 1「Keycloak 接入 + 身份对齐」与报告 P0（认证安全整改）。

迁移策略
    身份权威逐步转移到 Keycloak，但业务库里的 sys_user 仍然是各业务表的外键，
    不能一次性废弃。因此这里做的是「令牌来自 Keycloak，用户对象仍取自本地库」：
    校验 Keycloak 令牌 → 按 preferred_username 找到本地用户 → 返回本地 User。

    这样业务代码（practice / reading / case_browse 等）一行都不用改，
    却已经在用 Keycloak 的口令策略、限流、会话与审计。
"""

import time
from typing import Any, Dict, Optional

import requests
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import User

_jwks_cache: Dict[str, Any] = {"client": None, "at": 0.0}
_JWKS_TTL = 600


def issuer() -> str:
    return (
        f"{settings.KEYCLOAK_BASE_URL.rstrip('/')}"
        f"/realms/{settings.KEYCLOAK_REALM}"
    )


def _jwk_client():
    """PyJWKClient 带缓存，避免每次校验都拉公钥"""
    now = time.time()
    if _jwks_cache["client"] and now - _jwks_cache["at"] < _JWKS_TTL:
        return _jwks_cache["client"]
    try:
        from jwt import PyJWKClient
    except ImportError:
        return None
    client = PyJWKClient(f"{issuer()}/protocol/openid-connect/certs")
    _jwks_cache["client"] = client
    _jwks_cache["at"] = now
    return client


def verify(token: str) -> Optional[dict]:
    """
    校验 Keycloak 签发的令牌。

    任何异常都返回 None——鉴权失败必须是拒绝，不能因为解析报错而放行。
    """
    if not token:
        return None
    raw = token[7:] if token.lower().startswith("bearer ") else token

    try:
        import jwt
    except ImportError:
        return None

    client = _jwk_client()
    if client is None:
        return None

    try:
        key = client.get_signing_key_from_jwt(raw)
        return jwt.decode(
            raw, key.key, algorithms=["RS256"], issuer=issuer(),
            # aud 随客户端变化，权限以 realm 角色为准
            options={"verify_aud": False},
        )
    except Exception:
        return None


def roles_of(claims: dict) -> set:
    return set((claims.get("realm_access") or {}).get("roles") or [])


def resolve_local_user(db: Session, token: str) -> Optional[User]:
    """
    Keycloak 令牌 → 本地 User 对象。

    以 preferred_username 关联；找不到对应本地用户时返回 None，
    不自动建号——避免 Keycloak 里误建的账号凭空获得业务数据权限。
    """
    claims = verify(token)
    if not claims:
        return None

    username = claims.get("preferred_username") or ""
    if not username:
        return None

    user = db.query(User).filter(User.username == username).first()
    if user is None or user.is_active is False:
        return None
    return user


def password_login(username: str, password: str) -> Dict[str, Any]:
    """
    用 Keycloak 校验用户名口令（Resource Owner Password Credentials）。

    :return: {"ok": bool, "data": 令牌信息, "error": 错误码, "message": 中文提示}

    说明：ROPC 拿不到 Keycloak 的登录页，因此「首次登录强制改密」这类
    必需动作无法在此流程中完成——Keycloak 会直接返回
    "Account is not fully set up"。这属于预期行为，提示信息里会讲清楚，
    前端应引导用户走 OIDC 授权码流程改密。
    """
    url = f"{issuer()}/protocol/openid-connect/token"
    try:
        r = requests.post(
            url,
            data={
                "grant_type": "password",
                "client_id": settings.KEYCLOAK_CLIENT_ID,
                "client_secret": settings.KEYCLOAK_CLIENT_SECRET,
                "username": username,
                "password": password,
            },
            timeout=20,
        )
    except requests.RequestException as exc:
        return {"ok": False, "error": "unreachable",
                "message": f"认证服务不可用：{exc}"}

    if r.status_code == 200:
        return {"ok": True, "data": r.json()}

    try:
        body = r.json()
    except ValueError:
        body = {}
    desc = body.get("error_description", "")

    if "not fully set up" in desc:
        message = "该账号需要先完成首次设置（如修改初始密码），请使用统一登录页面完成后再试"
    elif r.status_code in (400, 401):
        message = "用户名或密码错误"
    elif r.status_code == 403:
        message = "账号已被锁定或禁用，请联系管理员"
    else:
        message = f"登录失败（{r.status_code}）"

    return {"ok": False, "error": body.get("error", "invalid_grant"),
            "message": message}
