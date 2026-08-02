# -*- coding: utf-8 -*-
"""
LTI 1.3 启动校验

启动令牌由外部平台签发，是本系统唯一一处「身份来自外部」的入口。
少验一条，攻击者就能以任意学员身份进来看金标准、
或往别人的成绩单里写分数。所以每条防线都要有测试证明它挡得住。

这里用真的 RSA 密钥签真的 JWT，不打桩验签 ——
打桩测出来的是「我们以为的验签」，不是实际的验签。
"""

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import LtiNonce, LtiPlatform, Role, RoleEnum, User
from app.services import lti_service

ISSUER = "https://moodle.example.edu"
CLIENT_ID = "huiyan-tool-001"
DEPLOYMENT_ID = "7:abcdef"

_platform_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture()
def platform(db):
    p = LtiPlatform(
        name="示范 Moodle",
        issuer=ISSUER,
        client_id=CLIENT_ID,
        deployment_id=DEPLOYMENT_ID,
        auth_login_url=f"{ISSUER}/mod/lti/auth.php",
        auth_token_url=f"{ISSUER}/mod/lti/token.php",
        key_set_url=f"{ISSUER}/mod/lti/certs.php",
        auto_provision=False,
        enabled=True,
    )
    db.add(p)
    db.commit()
    return p


@pytest.fixture(autouse=True)
def _stub_platform_jwks(monkeypatch):
    """
    只桩掉「去平台拉公钥」这一次网络请求，验签本身仍是真的：
    用真私钥签、真公钥验，签名不对就必须失败。
    """
    class _Key:
        key = _platform_key.public_key()

    class _Client:
        def get_signing_key_from_jwt(self, token):
            return _Key()

    monkeypatch.setattr(lti_service, "_jwk_client", lambda url: _Client())


def make_token(nonce="n-1", **overrides):
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "aud": CLIENT_ID,
        "sub": "moodle-user-42",
        "exp": now + 300,
        "iat": now,
        "nonce": nonce,
        "email": "stu@example.edu",
        "name": "学员甲",
        lti_service.VERSION_CLAIM: "1.3.0",
        lti_service.MESSAGE_TYPE_CLAIM: "LtiResourceLinkRequest",
        lti_service.DEPLOYMENT_CLAIM: DEPLOYMENT_ID,
        lti_service.ROLES_CLAIM: [
            "http://purl.imsglobal.org/vocab/lis/v2/membership#Learner"
        ],
    }
    # _key 先取出来：留在 overrides 里会被当成一个 claim 写进 JWT
    key = overrides.pop("_key", _platform_key)
    claims.update(overrides)
    return jwt.encode(claims, key, algorithm="RS256")


def _validate(db, token, nonce="n-1", got_state=None, use_cookie=True):
    """
    state 现在是自签的 JWT，不再是任意字符串 —— 校验的权威依据是
    它上面的签名，因为浏览器默认拦截第三方 Cookie，
    iframe 启动时 Cookie 常常带不回来。
    """
    signed = lti_service.issue_state(nonce)
    received = signed if got_state is None else got_state
    return lti_service.validate_launch(
        db, token,
        expected_state=signed if use_cookie else None,
        received_state=received,
        expected_nonce=nonce if use_cookie else None,
    )


# --------------------------------------------------------------------------
# 正常路径
# --------------------------------------------------------------------------

def test_valid_launch_passes(db, platform):
    p, claims = _validate(db, make_token())
    assert p.id == platform.id
    assert claims["sub"] == "moodle-user-42"


# --------------------------------------------------------------------------
# 每条防线
# --------------------------------------------------------------------------

def test_wrong_signature_is_rejected(db, platform):
    """别人的私钥签的令牌必须打不开"""
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(HTTPException) as exc:
        _validate(db, make_token(_key=other))
    assert exc.value.status_code == 403


def test_unregistered_issuer_is_rejected(db, platform):
    with pytest.raises(HTTPException):
        _validate(db, make_token(iss="https://evil.example.com"))


def test_unregistered_deployment_is_rejected(db, platform):
    """
    issuer 对但 deployment 没登记 —— 这是「在别处装了一个同名工具」
    最常见的形态，不能因为 issuer 对就放行。
    """
    with pytest.raises(HTTPException) as exc:
        _validate(db, make_token(**{lti_service.DEPLOYMENT_CLAIM: "99:other"}))
    assert exc.value.status_code == 403


def test_wrong_audience_is_rejected(db, platform):
    with pytest.raises(HTTPException):
        _validate(db, make_token(aud="someone-else"))


def test_expired_token_is_rejected(db, platform):
    now = int(time.time())
    with pytest.raises(HTTPException):
        _validate(db, make_token(exp=now - 3600, iat=now - 7200))


def test_state_mismatch_is_rejected(db, platform):
    """
    state 证明这次启动是我们自己发起的登录换来的。
    没有它，任何人都能把一个抓到的 id_token 直接 POST 进来。
    """
    with pytest.raises(HTTPException):
        _validate(db, make_token(), got_state=lti_service.issue_state("别的登录"))


def test_missing_state_is_rejected(db, platform):
    """Cookie 丢失时不能「宽容放行」，那等于这道防线不存在"""
    with pytest.raises(HTTPException):
        _validate(db, make_token(), got_state="", use_cookie=False)


def test_nonce_mismatch_is_rejected(db, platform):
    with pytest.raises(HTTPException):
        _validate(db, make_token(nonce="n-x"), nonce="n-1")


def test_replayed_token_is_rejected(db, platform):
    """
    同一个令牌用第二次必须失败。
    只验签名和过期时间挡不住重放 —— 签名依然有效。
    """
    token = make_token(nonce="n-replay")
    _validate(db, token, nonce="n-replay")
    db.commit()
    with pytest.raises(HTTPException) as exc:
        _validate(db, token, nonce="n-replay")
    assert "重放" in exc.value.detail


def test_nonce_is_recorded(db, platform):
    _validate(db, make_token(nonce="n-keep"), nonce="n-keep")
    db.commit()
    assert db.query(LtiNonce).filter(LtiNonce.nonce == "n-keep").first()


def test_wrong_message_type_is_rejected(db, platform):
    with pytest.raises(HTTPException):
        _validate(db, make_token(**{
            lti_service.MESSAGE_TYPE_CLAIM: "LtiDeepLinkingRequest"
        }))


def test_wrong_lti_version_is_rejected(db, platform):
    """LTI 1.1 的安全模型完全不同，不能按 1.3 处理"""
    with pytest.raises(HTTPException):
        _validate(db, make_token(**{lti_service.VERSION_CLAIM: "1.1.0"}))


def test_disabled_platform_is_rejected(db, platform):
    platform.enabled = False
    db.commit()
    with pytest.raises(HTTPException):
        _validate(db, make_token())


# --------------------------------------------------------------------------
# 角色映射
# --------------------------------------------------------------------------

@pytest.mark.parametrize("role,expected", [
    ("http://purl.imsglobal.org/vocab/lis/v2/membership#Instructor", True),
    ("http://purl.imsglobal.org/vocab/lis/v2/membership#TeachingAssistant", True),
    ("http://purl.imsglobal.org/vocab/lis/v2/membership#Learner", False),
    ("http://purl.imsglobal.org/vocab/lis/v2/system/person#None", False),
])
def test_role_mapping(role, expected):
    assert lti_service.is_teacher_roles([role]) is expected


def test_unknown_role_is_not_teacher():
    """认不出的角色一律按学员处理；判断错了学员会直接看到金标准"""
    assert lti_service.is_teacher_roles(["something-new"]) is False
    assert lti_service.is_teacher_roles([]) is False
    assert lti_service.is_teacher_roles(None) is False


# --------------------------------------------------------------------------
# 身份映射
# --------------------------------------------------------------------------

def _seed_user(db, email):
    role = Role(code=RoleEnum.STUDENT.value, name="学员")
    db.add(role)
    db.flush()
    u = User(username="stu", password_hash="x", email=email, role_id=role.id)
    db.add(u)
    db.commit()
    return u


def test_existing_user_matched_by_email(db, platform):
    u = _seed_user(db, "stu@example.edu")
    _, claims = _validate(db, make_token())
    assert lti_service.resolve_user(db, platform, claims).id == u.id


def test_no_auto_provision_by_default(db, platform):
    """
    默认不自动建号：教学系统里凭空多出来的账号成绩归属说不清，
    而且谁都能在自己的 Moodle 上装一个慧眼然后批量建号。
    """
    _, claims = _validate(db, make_token())
    assert lti_service.resolve_user(db, platform, claims) is None


def test_auto_provision_when_explicitly_enabled(db, platform):
    platform.auto_provision = True
    db.add(Role(code=RoleEnum.STUDENT.value, name="学员"))
    db.commit()
    _, claims = _validate(db, make_token())
    user = lti_service.resolve_user(db, platform, claims)
    assert user is not None
    assert user.email == "stu@example.edu"


def test_provisioned_user_has_no_usable_password(db, platform):
    """
    LTI 建的号只能从 LMS 启动。留一个可猜的弱口令等于开后门。
    """
    platform.auto_provision = True
    db.add(Role(code=RoleEnum.STUDENT.value, name="学员"))
    db.commit()
    _, claims = _validate(db, make_token())
    user = lti_service.resolve_user(db, platform, claims)
    from app.core.security import verify_password
    for guess in ("", "123456", "password", "!"):
        assert not verify_password(guess, user.password_hash)


# --------------------------------------------------------------------------
# 启动上下文与成绩回传
# --------------------------------------------------------------------------

def test_launch_context_is_recorded(db, platform):
    _, claims = _validate(db, make_token(**{
        lti_service.AGS_CLAIM: {
            "lineitem": "https://moodle.example.edu/mod/lti/services.php/2/lineitems/9/lineitem?type_id=3",
            "scope": [lti_service.AGS_SCORE_SCOPE],
        },
        lti_service.CONTEXT_CLAIM: {"id": "course-77"},
    }))
    launch = lti_service.record_launch(db, platform, claims, None)
    assert launch.context_id == "course-77"
    assert "lineitems/9" in launch.lineitem_url


def test_no_score_posted_without_ags_grant(db, platform):
    """
    平台没授予成绩服务时如实返回未回传，不假装成功 ——
    假装成功会让教师以为分数已经进作业栏了。
    """
    _, claims = _validate(db, make_token())
    launch = lti_service.record_launch(db, platform, claims, None)
    assert "未回传" in lti_service.post_score(db, launch, 88.0)


def test_no_score_posted_without_score_scope(db, platform):
    """有 lineitem 但没给写入权限，同样不能回传"""
    _, claims = _validate(db, make_token(**{
        lti_service.AGS_CLAIM: {
            "lineitem": "https://moodle.example.edu/lineitem",
            "scope": ["https://purl.imsglobal.org/spec/lti-ags/scope/result.readonly"],
        }
    }))
    launch = lti_service.record_launch(db, platform, claims, None)
    assert "未回传" in lti_service.post_score(db, launch, 88.0)


def test_custom_case_id_is_read(db, platform):
    _, claims = _validate(db, make_token(**{
        lti_service.CUSTOM_CLAIM: {"case_id": "42"}
    }))
    assert lti_service.target_case_id(claims) == 42


def test_missing_case_id_returns_none(db, platform):
    """教师没配病例就回病例列表，不猜一个塞给学员"""
    _, claims = _validate(db, make_token())
    assert lti_service.target_case_id(claims) is None
    _, claims2 = _validate(db, make_token(nonce="n-2", **{
        lti_service.CUSTOM_CLAIM: {"case_id": "not-a-number"}
    }), nonce="n-2")
    assert lti_service.target_case_id(claims2) is None


# --------------------------------------------------------------------------
# 工具端密钥
# --------------------------------------------------------------------------

def test_tool_jwks_is_public_only():
    """对外发布的 JWKS 里绝不能出现私钥分量"""
    jwks = lti_service.tool_jwks()
    key = jwks["keys"][0]
    assert key["kty"] == "RSA"
    assert key["alg"] == "RS256"
    for private_part in ("d", "p", "q", "dp", "dq", "qi"):
        assert private_part not in key, f"JWKS 泄露了私钥分量 {private_part}"


def test_unparseable_hash_does_not_raise():
    """
    哈希无法识别时必须返回 False，不能把异常抛给登录接口。

    LTI / 统一身份创建的账号故意不设可用口令，历史脏数据也可能
    留下非 bcrypt 的值。抛出去的话，有人拿这类账号尝试登录会得到
    500 而不是「密码错误」—— 既暴露了账号存在与否，
    也让日志堆满无意义的异常。
    """
    from app.core.security import verify_password
    for bad_hash in ("!", "", "plaintext", "$unknown$abc"):
        for guess in ("123456", "password", "!"):
            assert verify_password(guess, bad_hash) is False
