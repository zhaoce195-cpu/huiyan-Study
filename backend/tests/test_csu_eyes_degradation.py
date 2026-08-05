# -*- coding: utf-8 -*-
"""
算法服务不可用时的降级行为

推理服务经 SSH 反向隧道映射到本机端口。隧道断掉后端口仍在监听
（sshd 照常 accept），于是 TCP 连得上、HTTP 永远不回数据。

这种形态最容易做错：不预检就发正式请求，会一路耗到超时、再重试一次，
用户在界面上干等近三分钟才看到失败 —— 那三分钟里他不知道是在算，
还是早就坏了。
"""

import pytest
import requests
from fastapi import HTTPException

from app.services import csu_eyes_client as client


@pytest.fixture()
def files():
    return {"file": ("a.jpg", b"x", "image/jpeg")}


# --------------------------------------------------------------------------
# 预检
# --------------------------------------------------------------------------

def test_preflight_passes_when_service_answers(monkeypatch):
    monkeypatch.setattr(client.requests, "get", lambda *a, **k: object())
    assert client.preflight() is None


def test_preflight_detects_dead_tunnel(monkeypatch):
    """连得上但不回话 —— 隧道断了的典型形态"""
    def _timeout(*a, **k):
        raise requests.exceptions.Timeout()

    monkeypatch.setattr(client.requests, "get", _timeout)
    reason = client.preflight()
    assert reason and "无响应" in reason


def test_preflight_detects_refused(monkeypatch):
    def _refused(*a, **k):
        raise requests.exceptions.ConnectionError()

    monkeypatch.setattr(client.requests, "get", _refused)
    reason = client.preflight()
    assert reason and ("未启动" in reason or "不通" in reason)


def test_preflight_does_not_block_on_unexpected_response(monkeypatch):
    """
    返回了非预期内容不等于服务不可用（比如根路径本来就 404）。
    这种情况放行，让正式请求去判断 —— 预检只负责挡住「明确不可用」。
    """
    def _weird(*a, **k):
        raise ValueError("unexpected")

    monkeypatch.setattr(client.requests, "get", _weird)
    assert client.preflight() is None


# --------------------------------------------------------------------------
# 请求本身
# --------------------------------------------------------------------------

def test_dead_service_fails_fast(monkeypatch, files):
    """
    预检不通时立刻返回 503，且根本不发正式请求 ——
    不能让用户为一个已知坏掉的服务再等一个超时周期。
    """
    monkeypatch.setattr(client, "preflight", lambda: "算法服务无响应（推理通道可能已断开），请联系管理员")
    called = []
    monkeypatch.setattr(client.requests, "post",
                        lambda *a, **k: called.append(1))

    with pytest.raises(HTTPException) as exc:
        client._post_form_sync("http://x/api/v1/p", files=files)
    assert exc.value.status_code == 503
    assert "无响应" in exc.value.detail
    assert not called, "预检已判定不可用，不应再发正式请求"


def test_timeout_is_not_retried(monkeypatch, files):
    """
    超时不重试：已经等满一个超时周期，再来一遍只是把等待时间翻倍，
    结果不会变。此前正是这一条让用户干等了近三分钟（90 秒 × 2）。
    """
    monkeypatch.setattr(client, "preflight", lambda: None)
    attempts = []

    def _timeout(*a, **k):
        attempts.append(1)
        raise requests.exceptions.Timeout()

    monkeypatch.setattr(client.requests, "post", _timeout)

    with pytest.raises(HTTPException) as exc:
        client._post_form_sync("http://x/api/v1/p", files=files, timeout=5)
    assert exc.value.status_code == 504
    assert len(attempts) == 1, f"超时被重试了 {len(attempts)} 次"


def test_network_error_is_still_retried_once(monkeypatch, files):
    """
    连接类错误仍然重试一次：它可能是一次瞬时抖动，
    重试的代价很小（不像超时那样要再等满一个周期）。
    """
    monkeypatch.setattr(client, "preflight", lambda: None)
    attempts = []

    def _conn_err(*a, **k):
        attempts.append(1)
        raise requests.exceptions.ConnectionError("boom")

    monkeypatch.setattr(client.requests, "post", _conn_err)

    with pytest.raises(HTTPException):
        client._post_form_sync("http://x/api/v1/p", files=files, timeout=5)
    assert len(attempts) == 2
