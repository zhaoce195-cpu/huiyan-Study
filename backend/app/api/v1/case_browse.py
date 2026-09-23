"""
病例浏览检索路由
- 与前端 frontend/src/api/case-browse.ts 对齐
- 角色：STUDENT / TEACHER / ADMIN 均可访问
- 接口清单：
    GET    /case-browse/list                     病例分页检索
    GET    /case-browse/{caseId}                 病例详情
    PUT    /case-browse/{caseId}/archive         归档 / 取消归档
    PUT    /case-browse/{caseId}/gold-standard   修订金标准（存草稿 / 发布进实训）
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Path, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.common.response import success
from app.core.dependencies import CurrentUser, DbSession, require_roles
from app.db.models.user import RoleEnum
from app.schemas.case_browse import (
    CaseArchiveParams,
    CaseBrowseQuery,
    GoldStandardUpdate,
    SubjectLinkUpdate,
)
from app.services.case_browse_service import CaseBrowseService
from app.services.case_import_service import NAMING, CaseImportService

router = APIRouter(
    prefix="/case-browse",
    tags=["6. 病例浏览检索"],
    dependencies=[Depends(require_roles(RoleEnum.STUDENT, RoleEnum.TEACHER, RoleEnum.ADMIN))],
)


@router.get(
    "/list",
    summary="病例分页检索（多条件 + 关键词）",
    response_model=None,
)
def list_cases(
    current_user: CurrentUser,
    db: DbSession,
    keyword: Optional[str] = Query(None, description="关键词（编号/标题/描述/创建人/case_sn）"),
    category: Optional[str] = Query(None, description="病种分类"),
    drLevel: Optional[int] = Query(None, ge=0, le=4, description="DR 严重等级"),
    difficulty: Optional[str] = Query(None, description="难度：EASY/MEDIUM/HARD"),
    archiveStatus: Optional[str] = Query(None, description="归档状态：ACTIVE/ARCHIVED"),
    creatorRole: Optional[str] = Query(None, description="创建人员角色：STUDENT/TEACHER/ADMIN"),
    startTime: Optional[datetime] = Query(None, description="上传起始时间"),
    endTime: Optional[datetime] = Query(None, description="上传结束时间"),
    onlyIncomplete: bool = Query(False, description="只看影像不完整的病例"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=200),
):
    query = CaseBrowseQuery(
        keyword=keyword,
        category=category,  # type: ignore[arg-type]
        dr_level=drLevel,
        difficulty=difficulty,
        archive_status=archiveStatus,  # type: ignore[arg-type]
        creator_role=creatorRole,  # type: ignore[arg-type]
        start_time=startTime,
        end_time=endTime,
        only_incomplete=onlyIncomplete,
        page=page,
        page_size=pageSize,
    )
    data = CaseBrowseService.list_cases(db=db, user=current_user, query=query)
    return success(data=data.model_dump(by_alias=True))


class ImportCommitBody(BaseModel):
    token: str = Field(..., min_length=8)


@router.get("/import/template", summary="下载病例批量登记表")
def import_template(current_user: CurrentUser):
    CaseImportService.require_teacher(current_user)
    body = CaseImportService.template().encode("utf-8-sig")
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=case-register.csv"},
    )


@router.get("/import/rules", summary="影像命名要求")
def import_rules(current_user: CurrentUser):
    CaseImportService.require_teacher(current_user)
    return success(data={"naming": NAMING})


@router.post("/import/check", summary="入库前检查左右眼、质量、重复和患者信息")
async def import_check(
    current_user: CurrentUser,
    db: DbSession,
    sheet: UploadFile = File(...),
    images: List[UploadFile] = File(...),
):
    files = [(item.filename or "", await item.read()) for item in images]
    data = CaseImportService.check(db, current_user, await sheet.read(), files)
    return success(data=data, msg="检查完成")


@router.post("/import/commit", summary="把检查通过的病例写入病例库草稿")
def import_commit(
    body: ImportCommitBody,
    current_user: CurrentUser,
    db: DbSession,
):
    data = CaseImportService.commit(db, current_user, body.token)
    return success(data=data, msg=f"已导入 {data['count']} 例未发布草稿")


@router.get(
    "/{caseId}",
    summary="获取病例详情",
    response_model=None,
)
def get_detail(
    current_user: CurrentUser,
    db: DbSession,
    caseId: int = Path(..., ge=1),
):
    data = CaseBrowseService.get_detail(db=db, user=current_user, case_id=caseId)
    return success(data=data.model_dump(by_alias=True))


@router.put(
    "/{caseId}/archive",
    summary="病例归档 / 取消归档（TEACHER/ADMIN）",
    response_model=None,
)
def archive_case(
    params: CaseArchiveParams,
    current_user: CurrentUser,
    db: DbSession,
    caseId: int = Path(..., ge=1),
):
    data = CaseBrowseService.archive(
        db=db, user=current_user, case_id=caseId, params=params,
    )
    msg = "已归档" if params.archive_status == "ARCHIVED" else "已恢复"
    return success(data=data.model_dump(by_alias=True), msg=msg)


@router.put(
    "/{caseId}/subject",
    summary="把这张图和同一病人的其他时期连起来",
    response_model=None,
)
def set_subject(
    params: SubjectLinkUpdate,
    current_user: CurrentUser,
    db: DbSession,
    caseId: int = Path(..., ge=1),
):
    data = CaseBrowseService.set_subject(
        db=db, user=current_user, case_id=caseId, params=params,
    )
    return success(data=data.model_dump(by_alias=True), msg="已保存这次检查的病人编号和日期")


# ============================================================
#                       加入实训 / 移除实训
# ============================================================

# 仅 TEACHER / ADMIN 可写实训状态；学员调用直接 403
_train_write_dep = Depends(require_roles(RoleEnum.TEACHER, RoleEnum.ADMIN))


@router.post(
    "/{caseId}/join-training",
    summary="把病例加入实训库（TEACHER/ADMIN，幂等）",
    response_model=None,
    dependencies=[_train_write_dep],
)
def join_training(
    current_user: CurrentUser,
    db: DbSession,
    caseId: int = Path(..., ge=1),
):
    data = CaseBrowseService.join_training(
        db=db, user=current_user, case_id=caseId,
    )
    return success(
        data=data.model_dump(by_alias=True),
        msg="病例已成功加入实训",
    )


@router.delete(
    "/{caseId}/join-training",
    summary="从实训库移除该病例（TEACHER/ADMIN）",
    response_model=None,
    dependencies=[_train_write_dep],
)
def leave_training(
    current_user: CurrentUser,
    db: DbSession,
    caseId: int = Path(..., ge=1),
):
    data = CaseBrowseService.remove_from_training(
        db=db, user=current_user, case_id=caseId,
    )
    return success(
        data=data.model_dump(by_alias=True),
        msg="已从实训库移除",
    )


@router.put(
    "/{caseId}/gold-standard",
    summary="修订金标准：保存草稿或发布并加入实训（TEACHER/ADMIN）",
    response_model=None,
    dependencies=[_train_write_dep],
)
def update_gold_standard(
    params: GoldStandardUpdate,
    current_user: CurrentUser,
    db: DbSession,
    caseId: int = Path(..., ge=1),
):
    data = CaseBrowseService.update_gold_standard(
        db=db, user=current_user, case_id=caseId, params=params,
    )
    msg = "已发布并加入实训" if params.publish else "金标准草稿已保存"
    return success(data=data.model_dump(by_alias=True), msg=msg)
