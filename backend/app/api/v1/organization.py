"""
机构 / 机构申请路由
- POST /organization/apply                        (any_login)  普通用户提交申请
- GET  /organization/orgs                         (any_login)  申请下拉用机构列表
- GET  /organization/applications/mine            (any_login)  自己看自己的申请历史
- GET  /organization/applications                 (TEACHER/ADMIN)  后台审核列表
- POST /organization/applications/{id}/review     (ADMIN)         审核通过 / 驳回
"""

from typing import Optional

from fastapi import APIRouter, Depends, Path, Query

from app.common.response import success
from app.core.dependencies import CurrentUser, DbSession, get_current_user, require_roles
from app.db.models.user import RoleEnum
from app.schemas.organization import (
    OrgApplicationCreate,
    OrgApplicationReview,
)
from app.services.organization_service import OrganizationService

router = APIRouter(
    prefix="/organization",
    tags=["10. 机构申请"],
)


# 仅登录即可
any_login = Depends(get_current_user)
admin_only = Depends(require_roles(RoleEnum.ADMIN))
teacher_admin = Depends(require_roles(RoleEnum.TEACHER, RoleEnum.ADMIN))


# ============================================================
#                普通用户：机构列表 / 提交申请 / 我的申请
# ============================================================

@router.get(
    "/orgs",
    summary="机构列表（用于申请下拉）",
    response_model=None,
    dependencies=[any_login],
)
def list_orgs(
    db: DbSession,
    keyword: Optional[str] = Query(None, description="搜索关键词（机构名/编码）"),
):
    items = OrganizationService.list_orgs(db, keyword=keyword)
    return success(data=[it.model_dump(by_alias=True) for it in items])


@router.post(
    "/apply",
    summary="提交「申请加入机构」",
    response_model=None,
    dependencies=[any_login],
)
def apply_to_org(
    params: OrgApplicationCreate,
    current_user: CurrentUser,
    db: DbSession,
):
    out = OrganizationService.apply(db, user=current_user, params=params)
    return success(data=out.model_dump(by_alias=True), msg="申请已提交，请等待审核")


@router.get(
    "/applications/mine",
    summary="我的机构申请历史",
    response_model=None,
    dependencies=[any_login],
)
def list_my_applications(
    current_user: CurrentUser,
    db: DbSession,
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
):
    out = OrganizationService.list_my_applications(
        db, user_id=current_user.id, page=page, page_size=pageSize,
    )
    return success(data=out.model_dump(by_alias=True))


# ============================================================
#                管理后台：审核
# ============================================================

@router.get(
    "/applications",
    summary="后台：机构申请分页列表",
    response_model=None,
    dependencies=[teacher_admin],
)
def list_applications(
    db: DbSession,
    keyword: Optional[str] = Query(None),
    status: Optional[str] = Query(None, description="PENDING/APPROVED/REJECTED"),
    organizationId: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
):
    out = OrganizationService.list_for_admin(
        db,
        keyword=keyword,
        status_filter=status,
        organization_id=organizationId,
        page=page,
        page_size=pageSize,
    )
    return success(data=out.model_dump(by_alias=True))


@router.post(
    "/applications/{appId}/review",
    summary="后台：审核（通过 / 驳回）",
    response_model=None,
    dependencies=[admin_only],
)
def review_application(
    params: OrgApplicationReview,
    current_user: CurrentUser,
    db: DbSession,
    appId: int = Path(..., ge=1),
):
    out = OrganizationService.review(
        db, reviewer=current_user, application_id=appId, params=params,
    )
    return success(
        data=out.model_dump(by_alias=True),
        msg="已通过" if params.accept else "已驳回",
    )
