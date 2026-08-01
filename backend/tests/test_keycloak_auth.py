# -*- coding: utf-8 -*-
"""
Keycloak 身份对齐测试

对应方案 Phase 1「Keycloak 接入 + 身份对齐」与报告 P0（认证安全整改）。

这里只测不依赖运行中 Keycloak 的纯逻辑部分：令牌校验的失败路径、
角色解析、登录失败信息的可读性。与真实 Keycloak 的联调由
scripts/ 下的验证脚本负责。
"""

from unittest.mock import patch

import pytest

from app.services import keycloak_client


# --------------------------------------------------------------------------
# 令牌校验：失败必须是拒绝
# --------------------------------------------------------------------------

@pytest.mark.parametrize("token", ["", None, "not-a-jwt", "aaa.bbb.ccc"])
def test_verify_rejects_garbage(token):
    """
    任何无法解析的输入都必须返回 None（拒绝）。
    鉴权代码里最危险的 bug 是「解析出错就放行」。
    """
    assert keycloak_client.verify(token) is None


def test_verify_returns_none_when_jwks_unavailable():
    """取不到公钥时不能放行"""
    with patch.object(keycloak_client, "_jwk_client", return_value=None):
        assert keycloak_client.verify("a.b.c") is None


def test_issuer_composition():
    iss = keycloak_client.issuer()
    assert iss.endswith("/realms/" + keycloak_client.settings.KEYCLOAK_REALM)
    assert iss.startswith("http")


# --------------------------------------------------------------------------
# 角色解析
# --------------------------------------------------------------------------

def test_roles_of_reads_realm_access():
    claims = {"realm_access": {"roles": ["TEACHER", "offline_access"]}}
    assert keycloak_client.roles_of(claims) == {"TEACHER", "offline_access"}


@pytest.mark.parametrize("claims", [{}, {"realm_access": {}}, {"realm_access": {"roles": None}}])
def test_roles_of_is_tolerant(claims):
    assert keycloak_client.roles_of(claims) == set()


# --------------------------------------------------------------------------
# 本地用户解析
# --------------------------------------------------------------------------

def test_resolve_local_user_rejects_invalid_token():
    with patch.object(keycloak_client, "verify", return_value=None):
        assert keycloak_client.resolve_local_user(None, "x") is None


def test_resolve_local_user_requires_username_claim():
    with patch.object(keycloak_client, "verify", return_value={"sub": "abc"}):
        assert keycloak_client.resolve_local_user(None, "x") is None


def test_resolve_local_user_does_not_autocreate():
    """
    Keycloak 里有、本地库里没有的账号必须返回 None。
    自动建号会让误建的 Keycloak 账号凭空获得业务数据权限。
    """
    class FakeQuery:
        def filter(self, *a, **k):
            return self

        def first(self):
            return None

    class FakeDB:
        def query(self, *a, **k):
            return FakeQuery()

    with patch.object(keycloak_client, "verify",
                      return_value={"preferred_username": "ghost"}):
        assert keycloak_client.resolve_local_user(FakeDB(), "x") is None


def test_resolve_local_user_rejects_disabled_account():
    class FakeUser:
        username = "someone"
        is_active = False

    class FakeQuery:
        def filter(self, *a, **k):
            return self

        def first(self):
            return FakeUser()

    class FakeDB:
        def query(self, *a, **k):
            return FakeQuery()

    with patch.object(keycloak_client, "verify",
                      return_value={"preferred_username": "someone"}):
        assert keycloak_client.resolve_local_user(FakeDB(), "x") is None


# --------------------------------------------------------------------------
# 登录失败信息
# --------------------------------------------------------------------------

class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def _login_with(status_code, payload):
    with patch.object(keycloak_client.requests, "post",
                      return_value=FakeResponse(status_code, payload)):
        return keycloak_client.password_login("u", "p")


def test_login_success():
    r = _login_with(200, {"access_token": "t", "expires_in": 300})
    assert r["ok"] is True
    assert r["data"]["access_token"] == "t"


def test_login_wrong_password_message_is_actionable():
    r = _login_with(401, {"error": "invalid_grant",
                          "error_description": "Invalid user credentials"})
    assert r["ok"] is False
    assert "用户名或密码错误" in r["message"]


def test_login_not_fully_set_up_explains_what_to_do():
    """
    迁移后用户带 UPDATE_PASSWORD，ROPC 会返回这个错误。
    原始英文提示完全看不出要做什么，必须翻译成可执行的引导。
    """
    r = _login_with(400, {"error": "invalid_grant",
                          "error_description": "Account is not fully set up"})
    assert r["ok"] is False
    assert "首次设置" in r["message"] or "修改初始密码" in r["message"]


def test_login_locked_account_message():
    r = _login_with(403, {"error": "invalid_grant"})
    assert "锁定" in r["message"] or "禁用" in r["message"]


def test_login_unreachable_is_distinguishable():
    """
    「认证服务不可达」必须与「口令错误」区分开：
    前者可以降级本地校验，后者绝不能——否则限流形同虚设。
    """
    import requests as _requests

    with patch.object(keycloak_client.requests, "post",
                      side_effect=_requests.RequestException("boom")):
        r = keycloak_client.password_login("u", "p")
    assert r["ok"] is False
    assert r["error"] == "unreachable"
