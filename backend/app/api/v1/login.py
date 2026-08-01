"""
登录 / 注销路由
"""

from fastapi import APIRouter, Depends, Request, HTTPException, status

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
    """
    账号密码登录。

    迁移期行为（方案 Phase 1「身份对齐」）：
        KEYCLOAK_LOGIN_ENABLED=True 时先请 Keycloak 校验口令，
        这样口令策略、登录限流、会话时长与失败审计立即由 Keycloak 承担；
        校验通过后仍签发平台自有令牌，业务侧无需改动。

        Keycloak 不可达时回退到本地校验，避免认证服务抖动直接锁死整个平台；
        口令错误则不回退——否则限流形同虚设。
    """
    from app.core.config import settings

    client_ip = request.client.host if request.client else ""

    verified_by_keycloak = False
    if getattr(settings, "KEYCLOAK_LOGIN_ENABLED", False):
        from app.services import keycloak_client

        result = keycloak_client.password_login(params.username, params.password)
        if result["ok"]:
            verified_by_keycloak = True
        else:
            if result.get("error") == "unreachable":
                # 认证服务不可达 → 降级本地校验，并在日志中留痕
                import logging
                logging.getLogger("huiyan.auth").warning(
                    "Keycloak 不可达，本次登录回退本地校验：%s", result["message"],
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=result["message"],
                )

    data: LoginResponse = AuthService.login(
        db=db, params=params, client_ip=client_ip,
        password_already_verified=verified_by_keycloak,
    )
    return success(data=data.model_dump(), msg="登录成功")


@router.get(
    "/oidc/config",
    summary="统一身份登录配置（供前端发起 OIDC 授权码 + PKCE 流程）",
    response_model=None,
)
def oidc_config():
    """
    下发 OIDC 参数，避免前端硬编码。

    前端据此走授权码 + PKCE 流程，从而能使用 Keycloak 的登录页面——
    首次登录强制改密、账号锁定提示等必需动作只能在该页面完成，
    用户名口令直传（ROPC）拿不到这些能力。
    """
    from app.core.config import settings

    enabled = bool(getattr(settings, "KEYCLOAK_LOGIN_ENABLED", False))
    issuer = (
        f"{settings.KEYCLOAK_BASE_URL.rstrip('/')}"
        f"/realms/{settings.KEYCLOAK_REALM}"
    )
    return success(data={
        "enabled": enabled,
        "issuer": issuer,
        # 前端是公共客户端，走 PKCE，不持有密钥
        "clientId": "huiyan-frontend",
        "authorizationEndpoint": f"{issuer}/protocol/openid-connect/auth",
        "tokenEndpoint": f"{issuer}/protocol/openid-connect/token",
        "endSessionEndpoint": f"{issuer}/protocol/openid-connect/logout",
        "accountUrl": f"{settings.KEYCLOAK_BASE_URL.rstrip('/')}"
                      f"/realms/{settings.KEYCLOAK_REALM}/account",
    })


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
