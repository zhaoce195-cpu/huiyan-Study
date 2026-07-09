"""
学习资料 / 收藏 / 笔记 路由
- 角色：STUDENT / TEACHER / ADMIN 均可访问，权限在 service 细化
- 接口清单：
    资料：
      GET    /learning/resources                公共资料分页
      GET    /learning/resources/{id}           资料详情（阅读量+1）
      POST   /learning/resources                上传资料（TEACHER/ADMIN）
      PUT    /learning/resources/{id}           编辑资料（自己/ADMIN）
      DELETE /learning/resources/{id}           删除资料（自己/ADMIN）
    收藏：
      GET    /learning/favorites                我的收藏分页
      POST   /learning/favorites                收藏 / 重打标签
      DELETE /learning/favorites/{resourceId}   取消收藏
    笔记：
      GET    /learning/notes                    笔记列表
      POST   /learning/notes                    新建笔记
      GET    /learning/notes/{id}               笔记详情
      PUT    /learning/notes/{id}               编辑笔记
      DELETE /learning/notes/{id}               删除笔记
"""

from typing import Optional

from fastapi import APIRouter, Depends, Path, Query

from app.common.response import success
from app.core.dependencies import CurrentUser, DbSession, require_roles
from app.db.models.user import RoleEnum
from app.schemas.learning import (
    FavoriteListQuery,
    FavoriteParams,
    NoteCreateParams,
    NoteListQuery,
    NoteUpdateParams,
    ResourceCreateParams,
    ResourceListQuery,
    ResourceUpdateParams,
)
from app.services.learning_service import LearningService


router = APIRouter(
    prefix="/learning",
    tags=["9. 学习资料与笔记"],
    dependencies=[Depends(require_roles(
        RoleEnum.STUDENT, RoleEnum.TEACHER, RoleEnum.ADMIN,
    ))],
)


# ====================== 资料 ======================

@router.get("/resources", summary="公共学习资料分页", response_model=None)
def list_resources(
    current_user: CurrentUser,
    db: DbSession,
    keyword: Optional[str] = Query(None),
    resourceType: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    onlyMine: bool = Query(False),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=200),
):
    query = ResourceListQuery(
        keyword=keyword,
        resource_type=resourceType,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        only_mine=onlyMine,
        page=page,
        page_size=pageSize,
    )
    data = LearningService.list_resources(db=db, user=current_user, query=query)
    return success(data=data.model_dump(by_alias=True))


@router.get("/resources/{resourceId}", summary="资料详情", response_model=None)
def get_resource(
    current_user: CurrentUser,
    db: DbSession,
    resourceId: int = Path(..., ge=1),
):
    data = LearningService.get_resource(db=db, user=current_user, resource_id=resourceId)
    return success(data=data.model_dump(by_alias=True))


@router.post("/resources", summary="上传学习资料（TEACHER/ADMIN）", response_model=None)
def create_resource(
    params: ResourceCreateParams,
    current_user: CurrentUser,
    db: DbSession,
):
    data = LearningService.create_resource(db=db, user=current_user, params=params)
    return success(data=data.model_dump(by_alias=True), msg="上传成功")


@router.put("/resources/{resourceId}", summary="编辑学习资料", response_model=None)
def update_resource(
    params: ResourceUpdateParams,
    current_user: CurrentUser,
    db: DbSession,
    resourceId: int = Path(..., ge=1),
):
    data = LearningService.update_resource(
        db=db, user=current_user, resource_id=resourceId, params=params,
    )
    return success(data=data.model_dump(by_alias=True), msg="已更新")


@router.delete("/resources/{resourceId}", summary="删除学习资料", response_model=None)
def delete_resource(
    current_user: CurrentUser,
    db: DbSession,
    resourceId: int = Path(..., ge=1),
):
    LearningService.delete_resource(db=db, user=current_user, resource_id=resourceId)
    return success(msg="已删除")


# ====================== 收藏 ======================

@router.get("/favorites", summary="我的收藏分页", response_model=None)
def list_favorites(
    current_user: CurrentUser,
    db: DbSession,
    keyword: Optional[str] = Query(None),
    resourceType: Optional[str] = Query(None),
    label: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=200),
):
    query = FavoriteListQuery(
        keyword=keyword,
        resource_type=resourceType,  # type: ignore[arg-type]
        label=label,
        page=page,
        page_size=pageSize,
    )
    data = LearningService.list_favorites(db=db, user=current_user, query=query)
    return success(data=data.model_dump(by_alias=True))


@router.post("/favorites", summary="收藏 / 更新收藏标签", response_model=None)
def add_favorite(
    params: FavoriteParams,
    current_user: CurrentUser,
    db: DbSession,
):
    data = LearningService.add_favorite(db=db, user=current_user, params=params)
    return success(data=data.model_dump(by_alias=True), msg="已收藏")


@router.delete(
    "/favorites/{resourceId}",
    summary="取消收藏",
    response_model=None,
)
def remove_favorite(
    current_user: CurrentUser,
    db: DbSession,
    resourceId: int = Path(..., ge=1),
):
    LearningService.remove_favorite(db=db, user=current_user, resource_id=resourceId)
    return success(msg="已取消收藏")


# ====================== 笔记 ======================

@router.get("/notes", summary="笔记列表", response_model=None)
def list_notes(
    current_user: CurrentUser,
    db: DbSession,
    keyword: Optional[str] = Query(None),
    caseId: Optional[int] = Query(None, ge=1),
    resourceId: Optional[int] = Query(None, ge=1),
    userId: Optional[int] = Query(None, ge=1, description="ADMIN 可指定，其他角色忽略"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=200),
):
    query = NoteListQuery(
        keyword=keyword,
        case_id=caseId,
        resource_id=resourceId,
        user_id=userId,
        page=page,
        page_size=pageSize,
    )
    data = LearningService.list_notes(db=db, user=current_user, query=query)
    return success(data=data.model_dump(by_alias=True))


@router.post("/notes", summary="新建笔记", response_model=None)
def create_note(
    params: NoteCreateParams,
    current_user: CurrentUser,
    db: DbSession,
):
    data = LearningService.create_note(db=db, user=current_user, params=params)
    return success(data=data.model_dump(by_alias=True), msg="笔记已创建")


@router.get("/notes/{noteId}", summary="笔记详情", response_model=None)
def get_note(
    current_user: CurrentUser,
    db: DbSession,
    noteId: int = Path(..., ge=1),
):
    data = LearningService.get_note(db=db, user=current_user, note_id=noteId)
    return success(data=data.model_dump(by_alias=True))


@router.put("/notes/{noteId}", summary="编辑笔记", response_model=None)
def update_note(
    params: NoteUpdateParams,
    current_user: CurrentUser,
    db: DbSession,
    noteId: int = Path(..., ge=1),
):
    data = LearningService.update_note(
        db=db, user=current_user, note_id=noteId, params=params,
    )
    return success(data=data.model_dump(by_alias=True), msg="已更新")


@router.delete("/notes/{noteId}", summary="删除笔记", response_model=None)
def delete_note(
    current_user: CurrentUser,
    db: DbSession,
    noteId: int = Path(..., ge=1),
):
    LearningService.delete_note(db=db, user=current_user, note_id=noteId)
    return success(msg="已删除")
