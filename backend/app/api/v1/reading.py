"""
影像阅片路由
- 与前端 frontend/src/api/reading.ts 对齐
- 角色：STUDENT / TEACHER / ADMIN 均可访问，权限在 service 层细化
- 接口清单：
    GET    /reading/cases/{caseId}/source       获取病例影像源
    GET    /reading/list                        阅片记录分页
    GET    /reading/{recordId}                  阅片记录详情
    GET    /reading/cases/{caseId}/draft        获取当前用户最新草稿（阅片页恢复用）
    POST   /reading/save                        保存（draft）/ 提交（submit=true）
    POST   /reading/{recordId}/review           教师审核（TEACHER/ADMIN）
    DELETE /reading/{recordId}                  删除（自己 DRAFT 或 ADMIN）
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from app.common.response import success
from app.core.dependencies import CurrentUser, DbSession, require_roles
from app.db.models.user import RoleEnum
from app.schemas.reading import (
    ReadingListQuery,
    ReadingReviewParams,
    ReadingSaveParams,
)
from app.services.reading_service import ReadingService

router = APIRouter(
    prefix="/reading",
    tags=["7. 影像阅片"],
    dependencies=[Depends(require_roles(RoleEnum.STUDENT, RoleEnum.TEACHER, RoleEnum.ADMIN))],
)


@router.get(
    "/cases/{caseId}/source",
    summary="获取病例影像源（供前端 Cornerstone 加载）",
    response_model=None,
)
def get_image_source(
    current_user: CurrentUser,
    db: DbSession,
    caseId: int = Path(..., ge=1),
):
    data = ReadingService.get_image_source(db=db, user=current_user, case_id=caseId)
    return success(data=data.model_dump(by_alias=True))


@router.post(
    "/cases/{caseId}/quality-check",
    summary="评估病例原始影像的图像质量（先质量后诊断门控）",
    response_model=None,
)
async def check_image_quality(
    current_user: CurrentUser,
    db: DbSession,
    caseId: int = Path(..., ge=1),
):
    """
    调用 CSU-EYES 图像质量模型评估该病例的全部原始影像。

    算法服务不可用时不抛错：逐张记录失败原因，质量保持「未评估」，
    由界面如实呈现——绝不因为调用失败就把影像当作合格。
    """
    from app.services.image_quality_service import ImageQualityService

    data = await ImageQualityService.evaluate_case(db=db, case_id=caseId)
    return success(data=data, msg="质量评估完成")


@router.get(
    "/cases/{caseId}/diagnosis-form",
    summary="按病种取结构化诊断表单定义",
    response_model=None,
)
def diagnosis_form_def(
    current_user: CurrentUser,
    db: DbSession,
    caseId: int = Path(..., ge=1),
):
    """
    表单由配置定义、按病种加载，新增病种只加配置不改代码。

    字段顺序遵循报告建议：质量 → 主要结论 → 关键征象 → 分级 →
    置信度 → 处置，渐进展开而非一次铺开全部字段。
    """
    from app.common import diagnosis_form
    from app.db.models import TrainingCase

    case = db.query(TrainingCase).filter(TrainingCase.id == caseId).first()
    if not case:
        raise HTTPException(status_code=404, detail="病例不存在")
    return success(data=diagnosis_form.get_form(case.category))


@router.get(
    "/cases/{caseId}/draft",
    summary="恢复当前用户在该病例的最新阅片草稿（可能为空）",
    response_model=None,
)
def get_latest_draft(
    current_user: CurrentUser,
    db: DbSession,
    caseId: int = Path(..., ge=1),
    imageIndex: int = Query(0, ge=0),
):
    data = ReadingService.get_latest_draft(
        db=db, user=current_user, case_id=caseId, image_index=imageIndex,
    )
    return success(data=data.model_dump(by_alias=True) if data else None)


@router.get(
    "/list",
    summary="阅片记录分页查询",
    response_model=None,
)
def list_records(
    current_user: CurrentUser,
    db: DbSession,
    caseId: Optional[int] = Query(None, ge=1),
    userId: Optional[int] = Query(None, ge=1),
    status: Optional[str] = Query(None, description="DRAFT/SUBMITTED/REVIEWED"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=200),
):
    query = ReadingListQuery(
        case_id=caseId,
        user_id=userId,
        status=status,  # type: ignore[arg-type]
        page=page,
        page_size=pageSize,
    )
    data = ReadingService.list_records(db=db, user=current_user, query=query)
    return success(data=data.model_dump(by_alias=True))


@router.get(
    "/{recordId}",
    summary="阅片记录详情",
    response_model=None,
)
def get_detail(
    current_user: CurrentUser,
    db: DbSession,
    recordId: int = Path(..., ge=1),
):
    data = ReadingService.get_detail(db=db, user=current_user, record_id=recordId)
    return success(data=data.model_dump(by_alias=True))


@router.post(
    "/save",
    summary="保存阅片标注（DRAFT，submit=true 时为 SUBMITTED）",
    response_model=None,
)
def save_reading(
    params: ReadingSaveParams,
    current_user: CurrentUser,
    db: DbSession,
):
    data = ReadingService.save(db=db, user=current_user, params=params)
    msg = "已提交" if params.submit else "已保存"
    return success(data=data.model_dump(by_alias=True), msg=msg)


@router.post(
    "/{recordId}/review",
    summary="教师审核阅片记录（TEACHER/ADMIN）",
    response_model=None,
)
def review_reading(
    params: ReadingReviewParams,
    current_user: CurrentUser,
    db: DbSession,
    recordId: int = Path(..., ge=1),
):
    data = ReadingService.review(
        db=db, user=current_user, record_id=recordId, params=params,
    )
    return success(data=data.model_dump(by_alias=True), msg="审核完成")


@router.delete(
    "/{recordId}",
    summary="删除阅片记录（自己草稿 / ADMIN）",
    response_model=None,
)
def delete_reading(
    current_user: CurrentUser,
    db: DbSession,
    recordId: int = Path(..., ge=1),
):
    ReadingService.delete(db=db, user=current_user, record_id=recordId)
    return success(msg="已删除")
