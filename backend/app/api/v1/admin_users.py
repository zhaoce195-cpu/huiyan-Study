"""
管理员 · 用户账号
    GET    /admin/users                     分页列表
    POST   /admin/users                     新建账号
    POST   /admin/users/{userId}/reset-password  重置密码
    PUT    /admin/users/{userId}/active     停用 / 启用
"""

from typing import Optional

from fastapi import APIRouter, Depends, Path, Query, Request

from app.common.response import success
from app.core.dependencies import CurrentUser, DbSession, require_roles
from app.db.models.user import RoleEnum
from app.schemas.user import AdminSetActiveParams, AdminUserCreate
from app.services.admin_user_service import AdminUserService

router = APIRouter(
    prefix="/admin/users",
    tags=["13. 管理员用户账号"],
    dependencies=[Depends(require_roles(RoleEnum.ADMIN))],
)


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else ""


@router.get(
    "",
    summary="用户账号分页列表",
    response_model=None,
)
def list_users(
    current_user: CurrentUser,  # noqa: ARG001
    db: DbSession,
    keyword: Optional[str] = Query(None, description="姓名 / 账号 / 科室"),
    role: Optional[str] = Query(None, description="STUDENT / TEACHER / ADMIN"),
    isActive: Optional[bool] = Query(None, description="是否启用"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=200),
):
    data = AdminUserService.list_users(
        db,
        keyword=keyword,
        role=role,
        is_active=isActive,
        page=page,
        page_size=pageSize,
    )
    return success(data=data.model_dump(by_alias=True))


@router.post(
    "",
    summary="新建账号（STUDENT / TEACHER / ADMIN）",
    response_model=None,
)
def create_user(
    params: AdminUserCreate,
    current_user: CurrentUser,
    db: DbSession,
    request: Request,
):
    data = AdminUserService.create_user(
        db, operator=current_user, params=params, ip=_client_ip(request),
    )
    return success(data=data.model_dump(by_alias=True), msg="账号已创建")


@router.post(
    "/{userId}/reset-password",
    summary="重置密码：生成临时密码，下次登录必改",
    response_model=None,
)
def reset_password(
    current_user: CurrentUser,
    db: DbSession,
    request: Request,
    userId: int = Path(..., ge=1),
):
    data = AdminUserService.reset_password(
        db, operator=current_user, user_id=userId, ip=_client_ip(request),
    )
    return success(
        data=data.model_dump(by_alias=True),
        msg="已生成临时密码，请告知用户登录后立即修改",
    )


@router.put(
    "/{userId}/active",
    summary="停用 / 启用账号",
    response_model=None,
)
def set_active(
    params: AdminSetActiveParams,
    current_user: CurrentUser,
    db: DbSession,
    request: Request,
    userId: int = Path(..., ge=1),
):
    data = AdminUserService.set_active(
        db,
        operator=current_user,
        user_id=userId,
        params=params,
        ip=_client_ip(request),
    )
    msg = "账号已启用" if params.is_active else "账号已停用，将无法登录"
    return success(data=data.model_dump(by_alias=True), msg=msg)
