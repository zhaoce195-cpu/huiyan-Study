"""
学员开户申请
    POST /student-applications                 访客提交（公开）
    GET  /student-applications/status          按手机号查进度（公开）
    GET  /student-applications                 后台列表（ADMIN）
    POST /student-applications/{id}/review     通过 / 驳回（ADMIN）
"""

from typing import Optional

from fastapi import APIRouter, Depends, Path, Query, Request

from app.common.response import success
from app.core.dependencies import CurrentUser, DbSession, require_roles
from app.db.models.user import RoleEnum
from app.schemas.student_application import StudentAppCreate, StudentAppReview
from app.services.student_application_service import StudentApplicationService

router = APIRouter(
    prefix="/student-applications",
    tags=["14. 学员开户申请"],
)

admin_only = Depends(require_roles(RoleEnum.ADMIN))


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else ""


@router.post(
    "",
    summary="申请学员账号（公开，无需登录）",
    response_model=None,
)
def apply(params: StudentAppCreate, db: DbSession):
    data = StudentApplicationService.apply(db, params)
    return success(data=data.model_dump(by_alias=True), msg="申请已提交，请等待管理员审核")


@router.get(
    "/status",
    summary="按手机号查询申请进度（公开）",
    response_model=None,
)
def query_status(
    db: DbSession,
    phone: str = Query(..., min_length=11, max_length=20),
):
    data = StudentApplicationService.query_by_phone(db, phone)
    return success(data=data.model_dump(by_alias=True))


@router.get(
    "",
    summary="学员开户申请列表（ADMIN）",
    response_model=None,
    dependencies=[admin_only],
)
def list_apps(
    current_user: CurrentUser,  # noqa: ARG001
    db: DbSession,
    keyword: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=200),
):
    data = StudentApplicationService.list_apps(
        db, keyword=keyword, status_code=status, page=page, page_size=pageSize,
    )
    return success(data=data.model_dump(by_alias=True))


@router.post(
    "/{appId}/review",
    summary="审核学员开户申请（ADMIN）",
    response_model=None,
    dependencies=[admin_only],
)
def review(
    params: StudentAppReview,
    current_user: CurrentUser,
    db: DbSession,
    request: Request,
    appId: int = Path(..., ge=1),
):
    data = StudentApplicationService.review(
        db,
        reviewer=current_user,
        application_id=appId,
        params=params,
        ip=_client_ip(request),
    )
    msg = "已通过并开通学员账号" if params.accept else "已驳回，理由已短信告知申请人"
    return success(data=data.model_dump(by_alias=True), msg=msg)
