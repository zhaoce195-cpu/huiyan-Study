"""
微信小程序登录业务
=================
流程：
  1) 小程序端 wx.login() 拿到 code，调 POST /auth/wechat/login
  2) 后端用 appid+secret 调 jscode2session 换 openid
  3) openid 已绑定平台账号 → 直接签发正式 token（need_bind=False）
     openid 未绑定           → 下发短期绑定票据 ticket（need_bind=True）
  4) 前端引导用户输入已有账号密码，调 POST /auth/wechat/bind
     校验通过后把 openid 写入 sys_user.wx_openid，并签发正式 token

开发模拟模式：
  WECHAT_APPID / WECHAT_SECRET 任一为空时，直接把前端传来的 code 当作 openid，
  无需真实小程序 appid 即可在开发者工具/本地联调时跑通整套流程。
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
import requests
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.db.models import User, UserSetting
from app.schemas.user import LoginResponse, WechatLoginResponse
from app.services.auth_service import _build_user_out

logger = logging.getLogger(__name__)

_JSCODE2SESSION_URL = "https://api.weixin.qq.com/sns/jscode2session"
_BIND_TICKET_TYPE = "wx_bind"


def _is_mock_mode() -> bool:
    return not (settings.WECHAT_APPID and settings.WECHAT_SECRET)


async def _code2openid(code: str) -> str:
    """用 code 换取微信 openid；开发模拟模式下直接返回 code 本身。"""
    if _is_mock_mode():
        logger.warning("[wechat] 未配置 APPID/SECRET，进入开发模拟模式，code 直接作为 openid")
        return f"mock_{code}"[:64]

    def _do_request() -> dict:
        resp = requests.get(
            _JSCODE2SESSION_URL,
            params={
                "appid": settings.WECHAT_APPID,
                "secret": settings.WECHAT_SECRET,
                "js_code": code,
                "grant_type": "authorization_code",
            },
            timeout=settings.WECHAT_API_TIMEOUT_SEC,
        )
        resp.raise_for_status()
        return resp.json()

    try:
        data = await run_in_threadpool(_do_request)
    except requests.RequestException as e:  # noqa: BLE001
        logger.error("[wechat] jscode2session 网络异常：%s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="微信服务暂时不可用，请稍后再试",
        )

    openid = data.get("openid")
    if not openid:
        # 常见：errcode 40029 无效 code / 40163 code 已被使用
        logger.warning("[wechat] jscode2session 失败：%s", data)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"微信登录失败：{data.get('errmsg', '无效的登录凭证')}",
        )
    return openid


def _issue_bind_ticket(openid: str) -> str:
    """为未绑定的 openid 签发短期票据（仅用于 bind 接口）。"""
    payload = {
        "openid": openid,
        "type": _BIND_TICKET_TYPE,
        "exp": datetime.now(timezone.utc)
        + timedelta(minutes=settings.WECHAT_BIND_TICKET_TTL_MIN),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def _verify_bind_ticket(ticket: str) -> str:
    """校验绑定票据，返回其中的 openid。"""
    try:
        payload = jwt.decode(
            ticket, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="绑定票据已过期，请重新发起微信登录",
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="绑定票据无效"
        )
    if payload.get("type") != _BIND_TICKET_TYPE or not payload.get("openid"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="绑定票据无效"
        )
    return payload["openid"]


def _login_response_for(db: Session, user: User, client_ip: str = "") -> LoginResponse:
    """组装正式登录态（与账号密码登录一致）。"""
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="账号已被停用，请联系管理员"
        )
    if not user.role:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="账号未关联角色，请联系管理员",
        )
    if not user.setting:
        user.setting = UserSetting(user_id=user.id)
    user.last_login_at = datetime.now()
    user.last_login_ip = (client_ip or "")[:64]
    db.commit()
    db.refresh(user)

    token, expire_at = create_access_token(
        subject=user.id,
        extra={"username": user.username, "role": user.role.code},
    )
    return LoginResponse(
        token=token,
        token_type="Bearer",
        expires_at=expire_at,
        user_info=_build_user_out(user),
    )


class WechatService:
    """微信小程序登录业务"""

    @staticmethod
    async def login(db: Session, code: str, client_ip: str = "") -> WechatLoginResponse:
        openid = await _code2openid(code)
        user: Optional[User] = (
            db.query(User).filter(User.wx_openid == openid).first()
        )
        if user:
            return WechatLoginResponse(
                need_bind=False,
                login=_login_response_for(db, user, client_ip),
            )
        return WechatLoginResponse(need_bind=True, ticket=_issue_bind_ticket(openid))

    @staticmethod
    def bind(
        db: Session,
        ticket: str,
        username: str,
        password: str,
        client_ip: str = "",
    ) -> LoginResponse:
        openid = _verify_bind_ticket(ticket)

        # openid 可能已被其它流程绑定（并发/重复点击）→ 幂等返回登录态
        existing = db.query(User).filter(User.wx_openid == openid).first()
        if existing:
            return _login_response_for(db, existing, client_ip)

        user: Optional[User] = (
            db.query(User).filter(User.username == username).first()
        )
        if not user or not verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="账号或密码错误"
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="账号已被停用，请联系管理员"
            )

        # 一个微信号只允许绑定一个账号；若该账号已绑了别的微信号则拒绝。
        # 开发模拟模式下 openid=mock_{code}，每次 wx.login 的 code 都不同 → 允许覆盖重绑，便于联调。
        if user.wx_openid and user.wx_openid != openid and not _is_mock_mode():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="该账号已绑定其它微信，请联系管理员解绑",
            )

        user.wx_openid = openid
        return _login_response_for(db, user, client_ip)
