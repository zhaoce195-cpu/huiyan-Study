"""
教学实训分享路由
- POST /teaching/share                  (TEACHER/ADMIN) 创建临时分享
- POST /teaching/share/{id}/revoke      (TEACHER/ADMIN) 收回分享
- POST /teaching/submit                 (TEACHER/ADMIN) 提交入库申请
- GET  /teaching/my-shares              (TEACHER/ADMIN) 我的教学分享列表
- GET  /teaching/student/cases          (STUDENT)       学员可见病例
- GET  /teaching/student/cases/{id}     (STUDENT)       学员查看病例详情
- GET  /teaching/admin/reviews          (ADMIN)         审核列表
- POST /teaching/admin/reviews/{id}     (ADMIN)         审核通过/驳回
- POST /teaching/admin/shelve/{id}      (ADMIN)         下架
"""

from typing import Optional

from fastapi import APIRouter, Depends, Path, Query, Request

from app.common.response import success
from app.core.dependencies import CurrentUser, DbSession, get_current_user, require_roles
from app.db.models.user import RoleEnum
from app.schemas.teaching import (
    TeachingReviewParams,
    TeachingShareCreate,
    TeachingSubmitCreate,
)
from app.services.teaching_service import TeachingService

router = APIRouter(
    prefix="/teaching",
    tags=["12. 教学实训分享"],
)

_teacher_dep = Depends(require_roles(RoleEnum.TEACHER, RoleEnum.ADMIN))
_admin_dep = Depends(require_roles(RoleEnum.ADMIN))
_student_dep = Depends(require_roles(RoleEnum.STUDENT, RoleEnum.TEACHER, RoleEnum.ADMIN))


def _ip(request: Request) -> str:
    return request.client.host if request.client else ""


@router.post("/share", dependencies=[_teacher_dep])
def create_share(params: TeachingShareCreate, db: DbSession, user: CurrentUser, request: Request):
    r = TeachingService.create_temp_share(db, user=user, params=params, ip=_ip(request))
    return success(data=r.model_dump(by_alias=True))


@router.post("/share/{share_id}/revoke", dependencies=[_teacher_dep])
def revoke_share(share_id: int = Path(...), db: DbSession = None, user: CurrentUser = None, request: Request = None):
    r = TeachingService.revoke_share(db, user=user, share_id=share_id, ip=_ip(request))
    return success(data=r.model_dump(by_alias=True))


@router.post("/submit", dependencies=[_teacher_dep])
def submit_for_review(params: TeachingSubmitCreate, db: DbSession, user: CurrentUser, request: Request):
    r = TeachingService.submit_for_review(db, user=user, params=params, ip=_ip(request))
    return success(data=r.model_dump(by_alias=True))


@router.get("/my-shares", dependencies=[_teacher_dep])
def my_shares(
    db: DbSession,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    share_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    r = TeachingService.list_for_teacher(
        db, user=user, page=page, page_size=page_size,
        share_type=share_type, status_filter=status,
    )
    return success(data=r.model_dump(by_alias=True))


@router.get("/student/cases", dependencies=[_student_dep])
def student_cases(
    db: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    r = TeachingService.list_for_student(db, page=page, page_size=page_size)
    return success(data=r.model_dump(by_alias=True))


@router.get("/student/cases/{share_id}", dependencies=[_student_dep])
def student_case_detail(share_id: int = Path(...), db: DbSession = None, user: CurrentUser = None, request: Request = None):
    r = TeachingService.get_student_case_detail(db, share_id=share_id, user=user, ip=_ip(request))
    return success(data=r.model_dump(by_alias=True))


@router.get("/admin/reviews", dependencies=[_admin_dep])
def admin_reviews(
    db: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
):
    r = TeachingService.list_for_admin(
        db, page=page, page_size=page_size,
        status_filter=status, keyword=keyword,
    )
    return success(data=r.model_dump(by_alias=True))


@router.post("/admin/reviews/{share_id}", dependencies=[_admin_dep])
def admin_review(params: TeachingReviewParams, share_id: int = Path(...), db: DbSession = None, user: CurrentUser = None, request: Request = None):
    r = TeachingService.review(db, reviewer=user, share_id=share_id, params=params, ip=_ip(request))
    return success(data=r.model_dump(by_alias=True))


@router.post("/admin/shelve/{share_id}", dependencies=[_admin_dep])
def admin_shelve(share_id: int = Path(...), db: DbSession = None, user: CurrentUser = None, request: Request = None):
    r = TeachingService.shelve(db, user=user, share_id=share_id, ip=_ip(request))
    return success(data=r.model_dump(by_alias=True))
