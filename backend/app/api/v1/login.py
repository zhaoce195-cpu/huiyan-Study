"""
登录 / 注销路由
"""

from fastapi import APIRouter, Depends, Request

from app.common.response import success
from app.core.dependencies import CurrentUser, DbSession
from app.schemas.user import (
    LoginRequest,
    LoginResponse,
    WechatBindRequest,
    WechatLoginRequest,
    WechatLoginResponse,
)
from app.services.auth_service import AuthService
from app.services.wechat_service import WechatService

router = APIRouter(prefix="/auth", tags=["1. 账号身份登录"])


@router.post(
    "/login",
    summary="账号密码登录",
    description="校验账号密码，成功返回 JWT 令牌、用户基础信息、用户角色",
    response_model=None,
)
def login(params: LoginRequest, request: Request, db: DbSession):
    client_ip = request.client.host if request.client else ""
    data: LoginResponse = AuthService.login(db=db, params=params, client_ip=client_ip)
    return success(data=data.model_dump(), msg="登录成功")


@router.post(
    "/logout",
    summary="退出登录",
    description="使当前 token 立即失效（加入黑名单）",
    response_model=None,
)
def logout(request: Request, current_user: CurrentUser):
    token = getattr(request.state, "access_token", "") or ""
    AuthService.logout(token)
    return success(msg="已退出登录")


@router.post(
    "/wechat/login",
    summary="微信小程序登录",
    description=(
        "小程序端 wx.login() 拿到 code 调用本接口。\n"
        "- openid 已绑定账号：返回 need_bind=false 与正式登录态 login\n"
        "- openid 未绑定    ：返回 need_bind=true 与短期绑定票据 ticket"
    ),
    response_model=None,
)
async def wechat_login(params: WechatLoginRequest, request: Request, db: DbSession):
    client_ip = request.client.host if request.client else ""
    data: WechatLoginResponse = await WechatService.login(
        db=db, code=params.code, client_ip=client_ip
    )
    msg = "登录成功" if not data.need_bind else "请绑定已有账号"
    return success(data=data.model_dump(), msg=msg)


@router.post(
    "/wechat/bind",
    summary="微信绑定已有账号",
    description="使用 login 接口返回的 ticket + 已有平台账号密码完成绑定，返回正式登录态",
    response_model=None,
)
def wechat_bind(params: WechatBindRequest, request: Request, db: DbSession):
    client_ip = request.client.host if request.client else ""
    data: LoginResponse = WechatService.bind(
        db=db,
        ticket=params.ticket,
        username=params.username,
        password=params.password,
        client_ip=client_ip,
    )
    return success(data=data.model_dump(), msg="绑定成功")
