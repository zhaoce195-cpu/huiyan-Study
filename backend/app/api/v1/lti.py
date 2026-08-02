# -*- coding: utf-8 -*-
"""
LTI 1.3 工具端接口

慧眼作为 LTI Tool 挂进 Moodle 等 LMS。学员在课程页点开活动，
经由这里落到阅片/练习工作台，做完的成绩回传到平台作业栏。

这些端点由平台以浏览器跳转/表单 POST 的方式调用，
不走本系统的登录态，因此不能挂 CurrentUser 依赖 ——
身份完全由平台签发的 id_token 决定，逐条校验见 lti_service。
"""

from typing import Optional

from fastapi import APIRouter, Form, Query, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse

from app.core.config import settings
from app.core.dependencies import DbSession
from app.services import lti_service
from app.services.op_log_service import OpLogService

router = APIRouter(prefix="/lti", tags=["LTI 1.3"])

STATE_COOKIE = "lti_state"
NONCE_COOKIE = "lti_nonce"


def _cookie_kw() -> dict:
    """
    state / nonce 的 Cookie 参数。

    SameSite 必须是 none：启动是平台站点向我们发起的跨站 POST。
    而 SameSite=None 又要求 Secure，所以只有 HTTPS 下 Cookie 才存得住。

    本地用 HTTP 联调时 Cookie 会被浏览器直接丢弃 —— 这不是配置错误，
    是浏览器的规则。所以校验的权威依据是 state 上的签名而不是 Cookie，
    Cookie 只在能带回来时作为额外加强（见 lti_service.validate_launch）。
    """
    https = (settings.PUBLIC_BASE_URL or "").startswith("https://")
    return dict(
        httponly=True,
        secure=https,
        samesite="none" if https else "lax",
        max_age=600,
        path="/",
    )


def _redirect_uri(request: Request) -> str:
    base = (settings.PUBLIC_BASE_URL or str(request.base_url)).rstrip("/")
    return f"{base}/api/v1/lti/launch"


@router.get("/jwks", summary="工具端公钥集（供平台验签客户端断言）")
def jwks():
    return JSONResponse(content=lti_service.tool_jwks())


@router.get("/register", summary="动态注册（LMS 管理员粘一个 URL 即可对接）")
def dynamic_register(
    request: Request,
    db: DbSession,
    openid_configuration: str = Query(..., description="平台的 OpenID 配置地址"),
    registration_token: Optional[str] = Query(None, description="平台下发的一次性注册令牌"),
):
    """
    LTI Advantage 动态注册。

    手工登记要填 issuer、client_id、deployment_id 和三个端点地址，
    任何一项填错都表现为「点了没反应」，现场排查极其费时。
    这里由协议本身交换元数据，管理员只需粘一个 URL。
    """
    base = (settings.PUBLIC_BASE_URL or str(request.base_url)).rstrip("/")
    try:
        platform = lti_service.dynamic_register(
            db=db,
            openid_configuration_url=openid_configuration,
            registration_token=registration_token,
            base_url=base,
        )
    except Exception as exc:
        db.rollback()
        detail = getattr(exc, "detail", None) or str(exc)
        return _message_page("注册失败", f"未能完成对接：{detail}")

    OpLogService.record(
        db, user=None, module="lti", action="register",
        detail=f"动态注册 {platform.issuer} client_id={platform.client_id}",
    )
    db.commit()

    # 平台在 iframe 里打开本页；注册完成必须回传这条消息，
    # 否则管理员看到的是一个卡住的空白框，不知道成没成
    html = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>注册完成</title></head><body style="font-family:system-ui;padding:24px">
<p>慧眼已完成注册，可以关闭本窗口。</p>
<script>
  if (window.opener && window.opener.postMessage) {
    window.opener.postMessage({ subject: 'org.imsglobal.lti.close' }, '*')
  } else if (window.parent && window.parent !== window) {
    window.parent.postMessage({ subject: 'org.imsglobal.lti.close' }, '*')
  }
</script></body></html>"""
    return Response(content=html, media_type="text/html; charset=utf-8")


@router.api_route("/login", methods=["GET", "POST"], summary="OIDC 第三方发起登录")
async def login(request: Request, db: DbSession):
    """
    平台发起登录。参数可能来自查询串（GET）或表单（POST），
    规范两种都允许，所以统一取。
    """
    form = {}
    if request.method == "POST":
        try:
            form = dict(await request.form())
        except Exception:
            form = {}
    params = {**dict(request.query_params), **form}

    url, state, nonce = lti_service.build_login_redirect(
        db=db,
        iss=params.get("iss") or "",
        login_hint=params.get("login_hint") or "",
        target_link_uri=params.get("target_link_uri") or "",
        client_id=params.get("client_id"),
        lti_message_hint=params.get("lti_message_hint"),
        redirect_uri=_redirect_uri(request),
    )
    db.commit()

    resp = RedirectResponse(url, status_code=302)
    kw = _cookie_kw()
    resp.set_cookie(STATE_COOKIE, state, **kw)
    resp.set_cookie(NONCE_COOKIE, nonce, **kw)
    return resp


@router.post("/launch", summary="资源启动（平台以表单 POST 提交 id_token）")
async def launch(
    request: Request,
    db: DbSession,
    id_token: str = Form(...),
    state: Optional[str] = Form(None),
):
    platform, claims = lti_service.validate_launch(
        db=db,
        id_token=id_token,
        expected_state=request.cookies.get(STATE_COOKIE),
        received_state=state,
        expected_nonce=request.cookies.get(NONCE_COOKIE),
    )

    user = lti_service.resolve_user(db, platform, claims)
    launch_row = lti_service.record_launch(db, platform, claims, user)

    if not user:
        db.commit()
        # 不静默放行也不自动建号：说清楚该找谁，比丢一个 403 有用
        return _message_page(
            "尚未开通账号",
            "您的 LMS 账号还没有对应的慧眼账号。请联系带教管理员，"
            "用同一邮箱开通后再从课程页进入。",
        )

    from app.core.security import create_access_token

    token, _ = create_access_token(
        user.id,
        extra={
            "username": user.username,
            "role": user.role.code if user.role else "",
            # 标记来源，便于审计区分「从 LMS 进来的会话」
            "lti_launch_id": launch_row.id,
        },
    )

    OpLogService.record(
        db,
        user=user,
        module="lti",
        action="launch",
        detail=(
            f"自 {platform.name or platform.issuer} 启动 "
            f"课程 {launch_row.context_id or '—'} "
            f"成绩回传 {'可用' if launch_row.lineitem_url else '未授予'}"
        ),
    )
    db.commit()

    case_id = lti_service.target_case_id(claims)
    # 跳前端而不是后端：开发期两者不同端口，同域部署时二者相同
    base = (
        settings.FRONTEND_BASE_URL
        or settings.PUBLIC_BASE_URL
        or str(request.base_url)
    ).rstrip("/")
    # 令牌经一次性中转页交给前端：放在 URL 里会进浏览器历史与
    # Referer，中转页拿到后立即写入本地存储并把地址替换掉
    target = f"{base}/lti-entry?token={token}&launchId={launch_row.id}"
    if case_id:
        target += f"&caseId={case_id}"

    resp = RedirectResponse(target, status_code=302)
    resp.delete_cookie(STATE_COOKIE, path="/")
    resp.delete_cookie(NONCE_COOKIE, path="/")
    return resp


def _message_page(title: str, body: str) -> Response:
    """启动失败时给用户一个能看懂的页面，而不是一段 JSON"""
    html = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>{title}</title><style>
body{{font-family:system-ui,sans-serif;background:#f5f7fa;margin:0;
display:flex;align-items:center;justify-content:center;height:100vh}}
.card{{background:#fff;padding:32px 40px;border-radius:8px;max-width:520px;
box-shadow:0 2px 12px rgba(0,0,0,.08)}}
h1{{font-size:18px;margin:0 0 12px;color:#1d2129}}
p{{color:#4e5969;line-height:1.8;margin:0}}
</style></head><body><div class="card"><h1>{title}</h1><p>{body}</p></div></body></html>"""
    return Response(content=html, media_type="text/html; charset=utf-8")
