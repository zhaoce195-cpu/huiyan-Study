# -*- coding: utf-8 -*-
"""
LTI 端点级集成测试

单元测试验的是「校验逻辑对不对」，这里验的是「整条链路接得上」：
登录发起的跳转参数、state/nonce 的 Cookie 往返、启动后的落地跳转。

这些地方出错的表现都是「点了没反应」或「一直说状态校验失败」，
在现场极难定位 —— 尤其 Cookie 的 SameSite：启动是平台站点发起的
跨站 POST，设成 lax 的话 Cookie 根本带不过来。
"""

import time
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.dependencies import get_current_user, get_db
from app.db.base import Base
from app.db.models import LtiPlatform, Role, RoleEnum, User
from app.main import app
from app.services import lti_service

ISSUER = "https://lms.test"
CLIENT_ID = "tool-abc"
DEPLOYMENT = "dep-1"

_platform_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture()
def client(monkeypatch):
    # 内存 SQLite 默认每条连接一个独立的库：种子数据写在一条连接上，
    # 请求用另一条连接就什么也查不到。StaticPool 让所有会话共用同一条连接。
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Maker = sessionmaker(bind=engine)

    seed = Maker()
    role = Role(code=RoleEnum.STUDENT.value, name="学员")
    seed.add(role)
    seed.flush()
    seed.add(User(username="stu", password_hash="x",
                  email="stu@example.edu", role_id=role.id))
    seed.add(LtiPlatform(
        name="测试平台", issuer=ISSUER, client_id=CLIENT_ID,
        deployment_id=DEPLOYMENT,
        auth_login_url=f"{ISSUER}/auth",
        auth_token_url=f"{ISSUER}/token",
        key_set_url=f"{ISSUER}/jwks",
        enabled=True,
    ))
    seed.commit()
    seed.close()

    def _db():
        s = Maker()
        try:
            yield s
        finally:
            s.close()

    class _Key:
        key = _platform_key.public_key()

    class _JwkClient:
        def get_signing_key_from_jwt(self, token):
            return _Key()

    monkeypatch.setattr(lti_service, "_jwk_client", lambda url: _JwkClient())

    app.dependency_overrides[get_db] = _db
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


def _id_token(nonce, **over):
    now = int(time.time())
    claims = {
        "iss": ISSUER, "aud": CLIENT_ID, "sub": "u-1",
        "exp": now + 300, "iat": now, "nonce": nonce,
        "email": "stu@example.edu", "name": "学员甲",
        lti_service.VERSION_CLAIM: "1.3.0",
        lti_service.MESSAGE_TYPE_CLAIM: "LtiResourceLinkRequest",
        lti_service.DEPLOYMENT_CLAIM: DEPLOYMENT,
        lti_service.ROLES_CLAIM: [
            "http://purl.imsglobal.org/vocab/lis/v2/membership#Learner"
        ],
    }
    claims.update(over)
    return jwt.encode(claims, _platform_key, algorithm="RS256")


# --------------------------------------------------------------------------
# JWKS
# --------------------------------------------------------------------------

def test_jwks_endpoint_serves_public_key(client):
    r = client.get("/api/v1/lti/jwks")
    assert r.status_code == 200
    key = r.json()["keys"][0]
    assert key["kty"] == "RSA" and key["kid"]
    # 私钥分量一个都不能出现
    assert not any(k in key for k in ("d", "p", "q", "dp", "dq", "qi"))


# --------------------------------------------------------------------------
# 登录发起
# --------------------------------------------------------------------------

def test_login_redirects_to_platform_with_required_params(client):
    r = client.get(
        "/api/v1/lti/login",
        params={"iss": ISSUER, "login_hint": "lh-1",
                "target_link_uri": "https://tool/launch", "client_id": CLIENT_ID},
        follow_redirects=False,
    )
    assert r.status_code == 302
    q = parse_qs(urlparse(r.headers["location"]).query)
    # 这几项少一个平台就不认，且报错信息通常毫无提示性
    assert q["response_type"] == ["id_token"]
    assert q["response_mode"] == ["form_post"]
    assert q["scope"] == ["openid"]
    assert q["prompt"] == ["none"]
    assert q["client_id"] == [CLIENT_ID]
    assert q["login_hint"] == ["lh-1"]
    assert q["state"] and q["nonce"]


def test_login_sets_state_cookies(client):
    """Cookie 仍要设：能带回来时作为额外加强"""
    r = client.get(
        "/api/v1/lti/login",
        params={"iss": ISSUER, "login_hint": "lh", "client_id": CLIENT_ID},
        follow_redirects=False,
    )
    raw = "; ".join(r.headers.get_list("set-cookie")).lower()
    assert "lti_state" in raw and "lti_nonce" in raw
    assert "httponly" in raw


def test_state_is_signed_and_self_contained(client):
    """
    校验的权威依据是 state 上的签名，不是 Cookie ——
    浏览器默认拦截第三方 Cookie，iframe 启动时 Cookie 往往
    根本带不回来。只靠 Cookie 的实现会「时好时坏」且无提示。
    """
    r = client.get(
        "/api/v1/lti/login",
        params={"iss": ISSUER, "login_hint": "lh", "client_id": CLIENT_ID},
        follow_redirects=False,
    )
    q = parse_qs(urlparse(r.headers["location"]).query)
    state, nonce = q["state"][0], q["nonce"][0]
    assert lti_service.read_state(state) == nonce


def test_forged_state_is_rejected(client):
    """别人自造的 state 必须验不过 —— 否则签名这道防线形同虚设"""
    import jwt as _jwt
    from cryptography.hazmat.primitives.asymmetric import rsa as _rsa
    other = _rsa.generate_private_key(public_exponent=65537, key_size=2048)
    fake = _jwt.encode(
        {"nonce": "n", "exp": int(time.time()) + 300, "purpose": "lti-state"},
        other, algorithm="RS256",
    )
    assert lti_service.read_state(fake) is None


def test_launch_works_without_cookies(client):
    """
    第三方 Cookie 被拦截时仍要能启动 —— 这是真实浏览器的默认行为，
    不是边缘情况。
    """
    state, nonce = _do_login(client)
    client.cookies.clear()
    r = client.post(
        "/api/v1/lti/launch",
        data={"id_token": _id_token(nonce), "state": state},
        follow_redirects=False,
    )
    assert r.status_code == 302, r.text[:200]
    assert "/lti-entry" in r.headers["location"]


def test_login_rejects_unknown_issuer(client):
    r = client.get(
        "/api/v1/lti/login",
        params={"iss": "https://evil.test", "login_hint": "x"},
        follow_redirects=False,
    )
    assert r.status_code != 302


# --------------------------------------------------------------------------
# 完整往返
# --------------------------------------------------------------------------

def _do_login(client):
    r = client.get(
        "/api/v1/lti/login",
        params={"iss": ISSUER, "login_hint": "lh", "client_id": CLIENT_ID},
        follow_redirects=False,
    )
    q = parse_qs(urlparse(r.headers["location"]).query)
    return q["state"][0], q["nonce"][0]


def test_full_launch_round_trip(client):
    """登录 → 启动 → 落到前端中转页，Cookie 由客户端自动带回"""
    state, nonce = _do_login(client)
    r = client.post(
        "/api/v1/lti/launch",
        data={"id_token": _id_token(nonce), "state": state},
        follow_redirects=False,
    )
    assert r.status_code == 302, r.text[:200]
    loc = r.headers["location"]
    assert "/lti-entry" in loc
    assert "token=" in loc


def test_launch_with_tampered_state_is_rejected(client):
    state, nonce = _do_login(client)
    r = client.post(
        "/api/v1/lti/launch",
        data={"id_token": _id_token(nonce), "state": state + "x"},
        follow_redirects=False,
    )
    assert r.status_code != 302


def test_launch_without_login_first_is_rejected(client):
    """没有先发起登录就直接 POST 启动 —— 没有 Cookie，必须挡住"""
    r = client.post(
        "/api/v1/lti/launch",
        data={"id_token": _id_token("n-any"), "state": "made-up"},
        follow_redirects=False,
    )
    assert r.status_code != 302


def test_replay_of_same_launch_is_rejected(client):
    """同一份启动数据重放第二次必须失败"""
    state, nonce = _do_login(client)
    token = _id_token(nonce)
    first = client.post("/api/v1/lti/launch",
                        data={"id_token": token, "state": state},
                        follow_redirects=False)
    assert first.status_code == 302

    state2, _ = _do_login(client)
    again = client.post("/api/v1/lti/launch",
                        data={"id_token": token, "state": state2},
                        follow_redirects=False)
    assert again.status_code != 302


def test_launch_carries_case_id_to_frontend(client):
    """教师在活动里配的病例号要一路带到工作台"""
    state, nonce = _do_login(client)
    r = client.post(
        "/api/v1/lti/launch",
        data={
            "id_token": _id_token(nonce, **{
                lti_service.CUSTOM_CLAIM: {"case_id": "89"}
            }),
            "state": state,
        },
        follow_redirects=False,
    )
    assert "caseId=89" in r.headers["location"]


def test_unknown_user_gets_readable_page_not_error(client, monkeypatch):
    """
    LMS 里有、慧眼里没有的用户：给一页说得清的提示，
    而不是丢一个 403 让学员去猜。
    """
    state, nonce = _do_login(client)
    r = client.post(
        "/api/v1/lti/launch",
        data={"id_token": _id_token(nonce, email="nobody@example.edu"),
              "state": state},
        follow_redirects=False,
    )
    assert r.status_code == 200
    assert "尚未开通账号" in r.text


def test_launch_is_audited(client):
    from app.db.models.operation_log import OperationLog

    state, nonce = _do_login(client)
    client.post("/api/v1/lti/launch",
                data={"id_token": _id_token(nonce), "state": state},
                follow_redirects=False)

    # 用同一个 engine 再开一个会话查审计
    gen = app.dependency_overrides[get_db]()
    db = next(gen)
    try:
        logs = db.query(OperationLog).filter(OperationLog.module == "lti").all()
        assert any(l.action == "launch" for l in logs)
    finally:
        gen.close()
