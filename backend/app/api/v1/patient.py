"""
病患手机号注册 / 验证码 / 我的体检报告 路由
- /auth/send_code     POST  发送验证码（模拟，固定 1234）
- /auth/register      POST  手机号 + 验证码 + 密码 注册（角色 PATIENT）
- /patient/my_reports GET   我的体检报告列表（按当前用户手机号）
- /patient/my_reports/{caseId} GET  报告详情
- /patient/my-reports         GET  我的体检报告列表（kebab 别名，按需求文档命名）
- /patient/report-pdf/{caseId} GET  预览 / 下载体检报告 PDF（仅本人可见）
- /patient/bind_case  POST  医生 / 管理员 给病例绑定病患手机号
"""

from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Path, Query
from fastapi.responses import Response

from app.common.response import success
from app.core.dependencies import CurrentUser, DbSession
from app.schemas.patient import (
    BindCaseParams,
    RegisterParams,
    SendCodeParams,
)
from app.services.patient_service import PatientService
from app.services.screening_service import ScreeningService


# ============================================================
# /auth/* —— 公共接口（无需 token）
# ============================================================

auth_router = APIRouter(prefix="/auth", tags=["1. 账号身份登录"])


@auth_router.post(
    "/send_code",
    summary="发送短信验证码（模拟，固定返回 1234）",
    response_model=None,
)
def send_code(params: SendCodeParams):
    data = PatientService.send_code(params)
    return success(
        data=data.model_dump(),
        msg="验证码已发送",
    )


@auth_router.post(
    "/register",
    summary="手机号注册（默认角色：PATIENT 病患）",
    response_model=None,
)
def register(params: RegisterParams, db: DbSession):
    data = PatientService.register(db=db, params=params)
    return success(data=data, msg="注册成功")


# ============================================================
# /patient/* —— 病患专属接口
# ============================================================

patient_router = APIRouter(prefix="/patient", tags=["10. 病患报告"])


@patient_router.get(
    "/my_reports",
    summary="我的体检报告列表（按当前用户手机号）",
    response_model=None,
)
def my_reports(
    current_user: CurrentUser,
    db: DbSession,
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=200),
    status: Optional[str] = Query(None),
):
    data = PatientService.my_reports(
        db=db, user=current_user,
        page=page, page_size=pageSize, status=status,
    )
    return success(data=data.model_dump(by_alias=True))


@patient_router.get(
    "/my_reports/{caseId}",
    summary="报告详情（仅本人可见）",
    response_model=None,
)
def my_report_detail(
    current_user: CurrentUser,
    db: DbSession,
    caseId: int = Path(..., ge=1),
):
    data = PatientService.my_report_detail(
        db=db, user=current_user, case_id=caseId,
    )
    return success(data=data.model_dump(by_alias=True))


@patient_router.post(
    "/bind_case",
    summary="医生 / 管理员 给病例绑定病患手机号",
    response_model=None,
)
def bind_case(
    params: BindCaseParams,
    current_user: CurrentUser,
    db: DbSession,
):
    data = PatientService.bind_case(db=db, user=current_user, params=params)
    return success(data=data, msg="已绑定")


# ============================================================
# 业务命名别名（与需求文档 /api/patient/my-reports 对齐，kebab）
# ============================================================

@patient_router.get(
    "/my-reports",
    summary="我的体检报告列表（kebab 别名，等价于 /my_reports）",
    response_model=None,
)
def my_reports_kebab(
    current_user: CurrentUser,
    db: DbSession,
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=200),
    status: Optional[str] = Query(None),
):
    data = PatientService.my_reports(
        db=db, user=current_user,
        page=page, page_size=pageSize, status=status,
    )
    return success(data=data.model_dump(by_alias=True))


# ============================================================
# 报告 PDF 下载 / 预览（仅本人可见）
# ============================================================

def _attach_filename_header(filename: str, *, inline: bool) -> dict:
    """RFC5987 兼容的 Content-Disposition，避免中文文件名乱码"""
    quoted = quote(filename, safe="")
    disp = "inline" if inline else "attachment"
    return {
        "Content-Disposition": (
            f"{disp}; filename=\"download.pdf\"; filename*=UTF-8''{quoted}"
        ),
        "Cache-Control": "no-store",
    }


@patient_router.get(
    "/report-pdf/{caseId}",
    summary="预览 / 下载本人体检报告 PDF",
    response_model=None,
)
def report_pdf(
    current_user: CurrentUser,
    db: DbSession,
    caseId: int = Path(..., ge=1),
    disposition: str = Query(
        "inline",
        regex="^(inline|attachment)$",
        description="inline=新标签页预览，attachment=下载",
    ),
):
    """
    病患取本人 PDF 报告。
    - 必须为该病例的 patient_user / 手机号本人
    - 报告状态必须为 confirmed
    - 文件丢失时会现场重新生成兜底
    """
    pdf_bytes, filename = ScreeningService.patient_report_pdf(
        db=db, user=current_user, case_id=caseId,
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers=_attach_filename_header(filename, inline=(disposition == "inline")),
    )
