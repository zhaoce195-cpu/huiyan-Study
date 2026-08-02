# -*- coding: utf-8 -*-
"""
LTI 1.3 工具端（慧眼作为 Tool，Moodle 等 LMS 作为 Platform）

采用 IMS Global 的 LTI 1.3 / LTI Advantage 标准，而不是自己实现一套对接：
不管院方现在有没有 LMS，支持这个标准本身就是国际背书；
换一家 LMS 时也不用重做集成。

三条链路：
    OIDC 第三方发起登录  →  /lti/login
    资源启动（带 id_token）→  /lti/launch
    成绩回传（AGS）      →  练习提交后异步推送

启动校验是安全边界。id_token 由平台签发，工具端必须逐条验：
签名、issuer、audience、有效期、nonce 未重放、state 与本次登录一致、
deployment_id 已登记。少验一条，攻击者就能以任意学员身份进来看金标准、
或往别人的成绩单里写分数。
"""

import json
import secrets
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import httpx
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException, status
from jwt import PyJWKClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import LtiLaunch, LtiNonce, LtiPlatform, RoleEnum, User

# 允许的时钟偏差。平台与工具分属不同机器，完全对时并不现实；
# 但放得太宽等于变相延长了 token 的有效期。
CLOCK_SKEW_SECONDS = 60

MESSAGE_TYPE_CLAIM = "https://purl.imsglobal.org/spec/lti/claim/message_type"
VERSION_CLAIM = "https://purl.imsglobal.org/spec/lti/claim/version"
DEPLOYMENT_CLAIM = "https://purl.imsglobal.org/spec/lti/claim/deployment_id"
ROLES_CLAIM = "https://purl.imsglobal.org/spec/lti/claim/roles"
CONTEXT_CLAIM = "https://purl.imsglobal.org/spec/lti/claim/context"
RESOURCE_LINK_CLAIM = "https://purl.imsglobal.org/spec/lti/claim/resource_link"
CUSTOM_CLAIM = "https://purl.imsglobal.org/spec/lti/claim/custom"
AGS_CLAIM = "https://purl.imsglobal.org/spec/lti-ags/claim/endpoint"
TARGET_LINK_CLAIM = "https://purl.imsglobal.org/spec/lti/claim/target_link_uri"

RESOURCE_LINK_REQUEST = "LtiResourceLinkRequest"
SUPPORTED_VERSION = "1.3.0"

AGS_SCORE_SCOPE = "https://purl.imsglobal.org/spec/lti-ags/scope/score"

# LTI 角色词表 → 本地角色。
# 只认明确的教师/助教角色，其余一律按学员处理 ——
# 角色判断错了，学员会直接看到金标准。
_TEACHER_ROLE_HINTS = (
    "#Instructor",
    "#TeachingAssistant",
    "#ContentDeveloper",
    "#Administrator",
    "#Mentor",
)


# ---------------------------------------------------------------------------
# 工具端密钥
# ---------------------------------------------------------------------------

def _key_path() -> Path:
    base = Path(__file__).resolve().parent.parent.parent / "keys"
    base.mkdir(parents=True, exist_ok=True)
    return base / "lti_tool_private.pem"


_private_key_cache: Optional[Any] = None


def tool_private_key():
    """
    工具端私钥。首次使用时自动生成并落盘。

    生产环境应当把这个文件作为密钥挂载进来，而不是让容器自己生成 ——
    容器重建会换掉密钥，已登记的平台随即验签失败。
    """
    global _private_key_cache
    if _private_key_cache is not None:
        return _private_key_cache

    path = _key_path()
    if path.exists():
        _private_key_cache = serialization.load_pem_private_key(
            path.read_bytes(), password=None,
        )
        return _private_key_cache

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    try:
        path.chmod(0o600)
    except Exception:
        # Windows 上 chmod 语义不同，失败不阻断；部署在 Linux 容器里才是正式环境
        pass
    _private_key_cache = key
    return key


def tool_key_id() -> str:
    """密钥 ID：由公钥指纹派生，换了密钥就自然换 kid"""
    import hashlib

    pub = tool_private_key().public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return hashlib.sha256(pub).hexdigest()[:16]


def tool_jwks() -> Dict[str, Any]:
    """对外发布的 JWKS。平台用它验证我们签发的客户端断言"""
    from jwt.algorithms import RSAAlgorithm

    pub = tool_private_key().public_key()
    jwk = json.loads(RSAAlgorithm.to_jwk(pub))
    jwk.update({"kid": tool_key_id(), "use": "sig", "alg": "RS256"})
    return {"keys": [jwk]}


# ---------------------------------------------------------------------------
# 平台查找
# ---------------------------------------------------------------------------

def find_platform(
    db: Session,
    issuer: str,
    client_id: Optional[str] = None,
    deployment_id: Optional[str] = None,
) -> Optional[LtiPlatform]:
    q = db.query(LtiPlatform).filter(
        LtiPlatform.issuer == issuer,
        LtiPlatform.enabled.is_(True),
    )
    if client_id:
        q = q.filter(LtiPlatform.client_id == client_id)
    if deployment_id:
        q = q.filter(LtiPlatform.deployment_id == deployment_id)
    return q.first()


# ---------------------------------------------------------------------------
# 第三方发起登录
# ---------------------------------------------------------------------------

STATE_TTL_SECONDS = 600


def issue_state(nonce: str) -> str:
    """把本次登录的 nonce 装进一个自签的短时效 JWT"""
    now = int(time.time())
    return jwt.encode(
        {"nonce": nonce, "iat": now, "exp": now + STATE_TTL_SECONDS,
         "jti": secrets.token_urlsafe(12), "purpose": "lti-state"},
        tool_private_key(),
        algorithm="RS256",
        headers={"kid": tool_key_id()},
    )


def read_state(state: Optional[str]) -> Optional[str]:
    """
    校验 state 并取回 nonce。伪造或过期一律返回 None。

    这里验的是「这个 state 确实是我们发出去的」。至于同一次启动
    只能用一次，由 nonce 的一次性保证 —— 两道各管一件事。
    """
    if not state:
        return None
    try:
        claims = jwt.decode(
            state,
            tool_private_key().public_key(),
            algorithms=["RS256"],
            options={"require": ["exp", "nonce"]},
        )
    except Exception:
        return None
    if claims.get("purpose") != "lti-state":
        return None
    return claims.get("nonce")


def build_login_redirect(
    db: Session,
    iss: str,
    login_hint: str,
    target_link_uri: str,
    client_id: Optional[str],
    lti_message_hint: Optional[str],
    redirect_uri: str,
) -> Tuple[str, str, str]:
    """
    构造去平台授权端点的跳转。

    :return: (跳转地址, state, nonce)
    state 与 nonce 由调用方写进 Cookie，启动回来时逐一核对。
    """
    platform = find_platform(db, iss, client_id)
    if not platform:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"未登记的 LTI 平台：{iss}",
        )
    if not platform.auth_login_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该平台未配置授权端点，无法发起登录",
        )

    nonce = secrets.token_urlsafe(24)
    # state 用工具私钥签成 JWT，把 nonce 装在里面。
    #
    # 不能只靠 Cookie：LTI 启动是 iframe 里的跨站请求，
    # 而浏览器已在默认拦截第三方 Cookie —— 纯 Cookie 方案
    # 在真实环境里会「时好时坏」，且没有任何错误提示。
    # 签名 state 让我们无论 Cookie 在不在都能认出自己发出的登录；
    # Cookie 仍然照设，能带回来时作为额外加强。
    state = issue_state(nonce)

    from urllib.parse import urlencode

    params = {
        "scope": "openid",
        "response_type": "id_token",
        "response_mode": "form_post",
        "prompt": "none",
        "client_id": platform.client_id,
        "redirect_uri": redirect_uri,
        "login_hint": login_hint,
        "state": state,
        "nonce": nonce,
    }
    if lti_message_hint:
        params["lti_message_hint"] = lti_message_hint
    # target_link_uri 由平台回传，用于确认最终落地页
    if target_link_uri:
        params["target_link_uri"] = target_link_uri

    sep = "&" if "?" in platform.auth_login_url else "?"
    return f"{platform.auth_login_url}{sep}{urlencode(params)}", state, nonce


# ---------------------------------------------------------------------------
# 启动校验
# ---------------------------------------------------------------------------

_jwk_clients: Dict[str, PyJWKClient] = {}


def _jwk_client(url: str) -> PyJWKClient:
    client = _jwk_clients.get(url)
    if client is None:
        # 缓存 JWKS，避免每次启动都去平台拉一次公钥
        client = PyJWKClient(url, cache_keys=True, lifespan=600)
        _jwk_clients[url] = client
    return client


def _consume_nonce(db: Session, nonce: str, issuer: str) -> None:
    """
    nonce 只能用一次。

    只验签名和过期时间挡不住重放 —— 被截获的 id_token 签名依然有效，
    在有效期内可以反复提交。
    """
    if not nonce:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="启动令牌缺少 nonce",
        )
    exists = db.query(LtiNonce.id).filter(LtiNonce.nonce == nonce).first()
    if exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="启动令牌已被使用过（疑似重放）",
        )
    db.add(LtiNonce(nonce=nonce, issuer=issuer))
    db.flush()


def validate_launch(
    db: Session,
    id_token: str,
    expected_state: Optional[str],
    received_state: Optional[str],
    expected_nonce: Optional[str],
) -> Tuple[LtiPlatform, Dict[str, Any]]:
    """
    校验平台签发的 id_token。任何一步不过就拒绝，不做「宽容处理」。
    """
    # state 先于一切：它证明这次启动是我们自己发起的登录换来的，
    # 而不是别人把一个 id_token 直接 POST 进来。
    #
    # 权威依据是 state 上的签名，不是 Cookie —— 浏览器默认拦截
    # 第三方 Cookie，iframe 启动时 Cookie 往往根本带不回来。
    state_nonce = read_state(received_state)
    if not state_nonce:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="启动状态校验失败，请从课程页重新进入",
        )
    # Cookie 能带回来时再加一道：它还能证明是同一个浏览器
    if expected_state and received_state != expected_state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="启动状态与本次登录不一致，请从课程页重新进入",
        )
    # 以 state 里的 nonce 为准；Cookie 里的只是冗余副本
    expected_nonce = expected_nonce or state_nonce
    if state_nonce != expected_nonce:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="启动状态与本次登录不一致，请从课程页重新进入",
        )

    try:
        unverified = jwt.decode(id_token, options={"verify_signature": False})
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="启动令牌格式错误",
        )

    issuer = unverified.get("iss") or ""
    aud = unverified.get("aud")
    client_id = aud[0] if isinstance(aud, list) and aud else aud
    deployment_id = unverified.get(DEPLOYMENT_CLAIM) or ""

    platform = find_platform(db, issuer, client_id, deployment_id)
    if not platform:
        # 动态注册时平台往往还没生成部署，注册记录里的 deployment_id 为空。
        # 只认领「同 issuer + 同 client_id 且尚未绑定任何部署」这一种情况；
        # 已经绑过别的部署就不再自动接纳 —— 否则任何人在自己的 LMS 里
        # 装一个同 client_id 的工具都能被认下来。
        pending = (
            db.query(LtiPlatform)
            .filter(
                LtiPlatform.issuer == issuer,
                LtiPlatform.client_id == client_id,
                LtiPlatform.deployment_id == "",
                LtiPlatform.enabled.is_(True),
            )
            .first()
        )
        if pending and deployment_id:
            bind_deployment(db, pending, deployment_id)
            platform = pending
    if not platform:
        # 分开报：issuer 对但 deployment 没登记，是最常见的「装了没登记」
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"未登记的 LTI 部署：{issuer} / {deployment_id}",
        )
    if not platform.key_set_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该平台未配置 JWKS 地址，无法验签",
        )

    try:
        signing_key = _jwk_client(platform.key_set_url).get_signing_key_from_jwt(id_token)
        claims = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=platform.client_id,
            issuer=platform.issuer,
            leeway=CLOCK_SKEW_SECONDS,
            options={"require": ["iss", "aud", "exp", "iat", "sub"]},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="启动令牌已过期，请重新进入",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=f"启动令牌验签失败：{exc}",
        )

    # nonce 必须与本次登录发出的一致，且此前未被使用过
    nonce = claims.get("nonce") or ""
    if expected_nonce and nonce != expected_nonce:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="启动令牌 nonce 不匹配",
        )
    _consume_nonce(db, nonce, platform.issuer)

    if claims.get(VERSION_CLAIM) != SUPPORTED_VERSION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的 LTI 版本：{claims.get(VERSION_CLAIM)}",
        )
    if claims.get(MESSAGE_TYPE_CLAIM) != RESOURCE_LINK_REQUEST:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的启动类型：{claims.get(MESSAGE_TYPE_CLAIM)}",
        )

    return platform, claims


# ---------------------------------------------------------------------------
# 身份映射
# ---------------------------------------------------------------------------

def is_teacher_roles(roles: Any) -> bool:
    """只认明确的教师类角色；判断错了学员会直接看到金标准"""
    items = roles if isinstance(roles, list) else [roles or ""]
    return any(
        any(hint.lower() in str(r).lower() for hint in _TEACHER_ROLE_HINTS)
        for r in items
    )


def resolve_user(
    db: Session,
    platform: LtiPlatform,
    claims: Dict[str, Any],
) -> Optional[User]:
    """
    把平台侧用户映射到本地账号。

    优先按邮箱匹配已有账号。找不到时是否自动建号由平台注册项控制，
    默认不建 —— 教学系统里凭空多出来的账号，成绩归属会说不清，
    而且谁都能在自己的 Moodle 上装一个慧眼然后批量建号。
    """
    email = (claims.get("email") or "").strip().lower()
    if email:
        hit = db.query(User).filter(User.email == email).first()
        if hit:
            return hit

    if not platform.auto_provision:
        return None

    sub = claims.get("sub") or ""
    if not sub:
        return None

    role_code = (
        RoleEnum.TEACHER.value
        if is_teacher_roles(claims.get(ROLES_CLAIM))
        else RoleEnum.STUDENT.value
    )
    from app.db.models import Role

    role = db.query(Role).filter(Role.code == role_code).first()
    username = f"lti_{abs(hash((platform.issuer, sub))) % (10 ** 12):012d}"
    user = User(
        username=username,
        # 通过 LTI 进来的账号不设本地口令：它只能从 LMS 启动，
        # 留一个可猜的弱口令等于开了后门
        password_hash="!",
        real_name=(claims.get("name") or "").strip()[:64],
        email=email or None,
        role_id=role.id if role else None,
    )
    db.add(user)
    db.flush()
    return user


def record_launch(
    db: Session,
    platform: LtiPlatform,
    claims: Dict[str, Any],
    user: Optional[User],
) -> LtiLaunch:
    """记下这次启动的上下文：成绩要在几分钟后回传，那时 id_token 已不在手上"""
    ags = claims.get(AGS_CLAIM) or {}
    launch = LtiLaunch(
        platform_id=platform.id,
        user_id=user.id if user else None,
        lti_user_id=str(claims.get("sub") or "")[:255],
        context_id=str((claims.get(CONTEXT_CLAIM) or {}).get("id") or "")[:255],
        resource_link_id=str((claims.get(RESOURCE_LINK_CLAIM) or {}).get("id") or "")[:255],
        lineitem_url=str(ags.get("lineitem") or "")[:1024],
        scope=json.dumps(ags.get("scope") or [], ensure_ascii=False),
        roles=json.dumps(claims.get(ROLES_CLAIM) or [], ensure_ascii=False),
    )
    db.add(launch)
    db.flush()
    return launch


def target_case_id(claims: Dict[str, Any]) -> Optional[int]:
    """
    取教师在 Moodle 里配置的病例号。

    LTI 的自定义参数（custom_case_id）是教师建活动时填的，
    没填就回到病例列表，不猜一个病例塞给学员。
    """
    custom = claims.get(CUSTOM_CLAIM) or {}
    raw = custom.get("case_id") or custom.get("caseId")
    try:
        value = int(str(raw).strip())
        return value if value > 0 else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 动态注册（LTI Advantage Dynamic Registration）
#
# 手工登记要填 issuer、client_id、deployment_id、三个端点地址，
# 任何一项填错都表现为「点了没反应」，现场排查极其费时。
# 动态注册让管理员在 LMS 里粘一个 URL 就完成对接，
# 双方的元数据由协议本身交换。
# ---------------------------------------------------------------------------

def tool_configuration(base_url: str) -> Dict[str, Any]:
    """按 OpenID Connect 动态注册规范描述本工具"""
    base = base_url.rstrip("/")
    return {
        "application_type": "web",
        "response_types": ["id_token"],
        "grant_types": ["client_credentials", "implicit"],
        "initiate_login_uri": f"{base}/api/v1/lti/login",
        "redirect_uris": [f"{base}/api/v1/lti/launch"],
        "client_name": "慧眼 AI 教学实训平台",
        "jwks_uri": f"{base}/api/v1/lti/jwks",
        "token_endpoint_auth_method": "private_key_jwt",
        "scope": AGS_SCORE_SCOPE,
        "https://purl.imsglobal.org/spec/lti-tool-configuration": {
            "domain": base.split("://", 1)[-1].split("/")[0],
            "target_link_uri": f"{base}/api/v1/lti/launch",
            "claims": ["iss", "sub", "name", "email"],
            "messages": [
                {
                    "type": "LtiResourceLinkRequest",
                    "target_link_uri": f"{base}/api/v1/lti/launch",
                }
            ],
        },
    }


def dynamic_register(
    db: Session,
    openid_configuration_url: str,
    registration_token: Optional[str],
    base_url: str,
) -> LtiPlatform:
    """
    向平台完成动态注册，并把结果落库。

    平台的 deployment_id 在注册响应里不一定给得出（Moodle 就是注册完
    才生成部署）。此时先落一条占位记录，等第一次启动带着真实的
    deployment_id 过来再补齐 —— 但绝不放行未登记的部署，
    补齐动作只认「issuer + client_id 已注册且尚无部署」这一种情况。
    """
    conf = httpx.get(openid_configuration_url, timeout=10.0)
    conf.raise_for_status()
    meta = conf.json()

    issuer = meta.get("issuer") or ""
    reg_endpoint = meta.get("registration_endpoint") or ""
    if not issuer or not reg_endpoint:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="平台的 OpenID 配置缺少 issuer 或注册端点",
        )

    headers = {"Content-Type": "application/json"}
    if registration_token:
        headers["Authorization"] = f"Bearer {registration_token}"

    resp = httpx.post(
        reg_endpoint,
        headers=headers,
        json=tool_configuration(base_url),
        timeout=15.0,
    )
    if resp.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"平台拒绝注册（HTTP {resp.status_code}）：{resp.text[:200]}",
        )
    registered = resp.json()

    client_id = registered.get("client_id") or ""
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="平台未返回 client_id",
        )

    tool_conf = registered.get(
        "https://purl.imsglobal.org/spec/lti-tool-configuration"
    ) or {}
    deployment_id = tool_conf.get("deployment_id") or ""

    existing = (
        db.query(LtiPlatform)
        .filter(LtiPlatform.issuer == issuer, LtiPlatform.client_id == client_id)
        .first()
    )
    platform = existing or LtiPlatform(issuer=issuer, client_id=client_id)
    platform.name = meta.get("issuer", "")[:128]
    platform.deployment_id = deployment_id
    platform.auth_login_url = meta.get("authorization_endpoint") or ""
    platform.auth_token_url = meta.get("token_endpoint") or ""
    platform.key_set_url = meta.get("jwks_uri") or ""
    platform.enabled = True
    if not existing:
        db.add(platform)
    db.flush()
    return platform


def bind_deployment(db: Session, platform: LtiPlatform, deployment_id: str) -> bool:
    """
    首次启动时补齐 deployment_id。

    只在「该注册尚无部署」时补。已经绑过别的部署就不再自动接纳 ——
    否则任何人在自己的 LMS 里装一个同 client_id 的工具都能被认下来。
    """
    if platform.deployment_id or not deployment_id:
        return False
    platform.deployment_id = deployment_id
    db.flush()
    return True


# ---------------------------------------------------------------------------
# AGS：成绩回传
# ---------------------------------------------------------------------------

def _client_assertion(platform: LtiPlatform) -> str:
    """用工具私钥签一个客户端断言，向平台换访问令牌"""
    now = int(time.time())
    return jwt.encode(
        {
            "iss": platform.client_id,
            "sub": platform.client_id,
            "aud": platform.auth_token_url,
            "iat": now,
            "exp": now + 300,
            "jti": secrets.token_urlsafe(16),
        },
        tool_private_key(),
        algorithm="RS256",
        headers={"kid": tool_key_id()},
    )


def _access_token(platform: LtiPlatform, scope: str) -> str:
    if not platform.auth_token_url:
        raise RuntimeError("平台未配置令牌端点")
    resp = httpx.post(
        platform.auth_token_url,
        data={
            "grant_type": "client_credentials",
            "client_assertion_type":
                "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": _client_assertion(platform),
            "scope": scope,
        },
        timeout=10.0,
    )
    resp.raise_for_status()
    token = resp.json().get("access_token")
    if not token:
        raise RuntimeError("平台未返回访问令牌")
    return token


def post_score(
    db: Session,
    launch: LtiLaunch,
    score: float,
    max_score: float = 100.0,
    comment: str = "",
) -> str:
    """
    把成绩回传到平台的作业栏。

    :return: 结果说明，供审计记录；不抛异常打断主流程 ——
             练习成绩已经在本系统落库了，回传失败是集成问题，
             不该让学员的提交跟着失败。
    """
    if not launch.lineitem_url:
        return "平台未授予成绩服务，未回传"
    try:
        scopes = json.loads(launch.scope or "[]")
    except Exception:
        scopes = []
    if AGS_SCORE_SCOPE not in scopes:
        return "平台未授予成绩写入权限，未回传"

    try:
        token = _access_token(
            db.query(LtiPlatform).filter(LtiPlatform.id == launch.platform_id).first(),
            AGS_SCORE_SCOPE,
        )
        # AGS 规定成绩发到 lineitem 的 /scores 子路径。
        # lineitem 地址可能自带查询串（Moodle 就会带 type_id），
        # 直接拼 "/scores" 会拼到查询串后面，必须先拆开。
        base, _, query = launch.lineitem_url.partition("?")
        scores_url = base.rstrip("/") + "/scores"
        if query:
            scores_url = f"{scores_url}?{query}"

        from datetime import datetime, timezone

        resp = httpx.post(
            scores_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/vnd.ims.lis.v1.score+json",
            },
            json={
                "userId": launch.lti_user_id,
                "scoreGiven": round(float(score), 2),
                "scoreMaximum": float(max_score),
                "activityProgress": "Completed",
                "gradingProgress": "FullyGraded",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "comment": comment or "",
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        return f"已回传：{score}/{max_score}"
    except Exception as exc:
        return f"回传失败：{exc}"
