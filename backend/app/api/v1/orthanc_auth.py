# -*- coding: utf-8 -*-
"""
Orthanc 授权服务端点

Orthanc 的 Authorization 插件把每次访问的准入决定委托给一个外部 Web 服务。
本模块实现该契约，用 Keycloak 签发的 JWT 做判定，从而让 PACS 与平台
共用同一套身份体系——不再依赖 orthanc.json 里的静态口令。

对应报告 P0（认证安全整改）与方案第 4.1 节 Keycloak 选型。

插件契约（POST <root>/v1/authorization）：
    请求  {"level": "study", "method": "get", "token-key": "...",
           "token-value": "Bearer xxx", "dicom-uid": "...", ...}
    响应  {"granted": true|false, "validity": <秒>}

设计要点
    1. 只认 Keycloak 签发且签名有效的令牌，JWKS 带缓存；
    2. 角色必须在 STUDENT / TEACHER / ADMIN 之内；
    3. 任何解析失败一律拒绝——鉴权失败必须是拒绝，不能是放行。
"""

import time
from typing import Any, Dict, Optional

import requests
from fastapi import APIRouter, Request

from app.core.config import settings

router = APIRouter(prefix="/orthanc-auth", tags=["14. PACS 授权"])

_ALLOWED_ROLES = {"STUDENT", "TEACHER", "ADMIN"}

# JWKS 缓存：避免每次请求都打 Keycloak
_jwks_cache: Dict[str, Any] = {"keys": None, "at": 0.0}
_JWKS_TTL = 600


def _jwks() -> Optional[dict]:
    now = time.time()
    if _jwks_cache["keys"] and now - _jwks_cache["at"] < _JWKS_TTL:
        return _jwks_cache["keys"]
    try:
        url = (
            f"{settings.KEYCLOAK_BASE_URL.rstrip('/')}"
            f"/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/certs"
        )
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        _jwks_cache["keys"] = r.json()
        _jwks_cache["at"] = now
        return _jwks_cache["keys"]
    except Exception:
        # 拿不到公钥时不能放行；返回 None 由调用方拒绝
        return None


def verify_token(raw: str) -> Optional[dict]:
    """
    校验 Keycloak JWT，返回声明；任何异常都返回 None（拒绝）。
    """
    if not raw:
        return None
    token = raw[7:] if raw.lower().startswith("bearer ") else raw

    try:
        import jwt
        from jwt import PyJWKClient
    except ImportError:
        return None

    keys = _jwks()
    if not keys:
        return None

    try:
        issuer = (
            f"{settings.KEYCLOAK_BASE_URL.rstrip('/')}"
            f"/realms/{settings.KEYCLOAK_REALM}"
        )
        signing_key = PyJWKClient(
            f"{issuer}/protocol/openid-connect/certs"
        ).get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=issuer,
            # Keycloak 的 aud 随客户端变化，这里只校验签名与签发者，
            # 具体权限由下面的角色判定负责
            options={"verify_aud": False},
        )
    except Exception:
        return None


def claims_allow_pacs(claims: Optional[dict]) -> bool:
    if not claims:
        return False
    roles = set((claims.get("realm_access") or {}).get("roles") or [])
    return bool(roles & _ALLOWED_ROLES)


@router.post("/v1/authorization", summary="Orthanc 授权插件回调")
async def authorize(request: Request):
    """
    Orthanc 每次访问受保护资源时调用本接口。

    返回 granted=false 即拒绝。validity 为决定的缓存秒数，
    设短一些以便令牌过期或角色调整能较快生效。
    """
    try:
        body = await request.json()
    except Exception:
        return {"granted": False, "validity": 0}

    claims = verify_token(body.get("token-value") or "")
    granted = claims_allow_pacs(claims)
    return {"granted": granted, "validity": 60 if granted else 0}


# ---------------------------------------------------------------------------
# 用户画像流程（新版插件走这条路径）
# ---------------------------------------------------------------------------
# 角色 → PACS 权限。学员只读，教师可上传，管理员全权。
_ROLE_PERMISSIONS = {
    "ADMIN": ["all"],
    "TEACHER": ["view", "download", "upload", "api-view", "edit-labels"],
    "STUDENT": ["view", "api-view"],
}


def _permissions_for(claims: dict) -> list:
    roles = set((claims.get("realm_access") or {}).get("roles") or [])
    for role in ("ADMIN", "TEACHER", "STUDENT"):
        if role in roles:
            return _ROLE_PERMISSIONS[role]
    return []


@router.post("/user/get-profile", summary="Orthanc 用户画像回调")
async def get_profile(request: Request):
    """
    插件用此接口换取当前令牌对应的用户身份与权限。

    校验不通过时返回空权限而不是报错——插件据此拒绝访问。
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    claims = verify_token(body.get("token-value") or "")
    if not claims_allow_pacs(claims):
        return {"name": "anonymous", "permissions": [], "validity": 0,
                "authorized-labels": []}

    return {
        "name": claims.get("preferred_username") or claims.get("sub") or "user",
        "permissions": _permissions_for(claims),
        "validity": 60,
        # 暂不按标签细分资源可见性；后续可按机构/班级下发标签
        "authorized-labels": ["*"],
    }


@router.post("/tokens/validate", summary="Orthanc 资源令牌校验回调")
async def validate_token(request: Request):
    """
    资源令牌（分享链接等）校验。当前不签发资源令牌，一律拒绝，
    访问统一走用户令牌。
    """
    return {"granted": False, "validity": 0}


@router.get("/health", summary="授权服务自检")
def health():
    """确认能取到 Keycloak 公钥；取不到时 PACS 会一律拒绝访问"""
    keys = _jwks()
    return {
        "keycloak": settings.KEYCLOAK_BASE_URL,
        "realm": settings.KEYCLOAK_REALM,
        "jwksReachable": bool(keys),
        "keyCount": len((keys or {}).get("keys") or []),
    }
