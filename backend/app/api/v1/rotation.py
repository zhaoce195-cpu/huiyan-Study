# -*- coding: utf-8 -*-
"""学员首页的轮转任务，以及教师布置。"""

from fastapi import APIRouter, Depends, Path

from app.common.response import success
from app.core.dependencies import CurrentUser, DbSession, require_roles
from app.db.models.user import RoleEnum
from app.schemas.rotation import RotationUpdate, StudentGroupUpdate, TaskCreate, TaskOrder
from app.services.rotation_service import RotationService


router = APIRouter(
    prefix="/rotation",
    tags=["轮转学习任务"],
    dependencies=[Depends(require_roles(
        RoleEnum.STUDENT, RoleEnum.TEACHER, RoleEnum.ADMIN,
    ))],
)


@router.get("/home", summary="学员或教师首页", response_model=None)
def home(current_user: CurrentUser, db: DbSession):
    data = RotationService.home(db, current_user)
    return success(data=data.model_dump(by_alias=True))


@router.get("/options", summary="可布置的病例和知识点", response_model=None)
def options(current_user: CurrentUser, db: DbSession):
    data = RotationService.options(db, current_user)
    return success(data=data.model_dump(by_alias=True))


@router.put("/students/{userId}/group", summary="设置学员的年级、轮转批次和带教组", response_model=None)
def set_student_group(
    current_user: CurrentUser,
    db: DbSession,
    params: StudentGroupUpdate,
    userId: int = Path(..., ge=1),
):
    data = RotationService.set_student_group(db, current_user, userId, params)
    return success(data=data.model_dump(by_alias=True), msg="分组已保存")


@router.put("/current", summary="修改本轮转截止日期和合格分", response_model=None)
def update_current(current_user: CurrentUser, db: DbSession, params: RotationUpdate):
    data = RotationService.update_rotation(db, current_user, params)
    return success(data=data.model_dump(by_alias=True))


@router.post("/tasks", summary="加入一项必做或拓展", response_model=None)
def add_task(current_user: CurrentUser, db: DbSession, params: TaskCreate):
    data = RotationService.add_task(db, current_user, params)
    return success(data=data.model_dump(by_alias=True))


@router.put("/tasks/order", summary="调整任务顺序", response_model=None)
def reorder_tasks(current_user: CurrentUser, db: DbSession, params: TaskOrder):
    data = RotationService.reorder(db, current_user, params)
    return success(data=data.model_dump(by_alias=True), msg="顺序已保存")


@router.post("/tasks/arrange", summary="按病谱从轻到重排列", response_model=None)
def arrange_tasks(current_user: CurrentUser, db: DbSession):
    data = RotationService.arrange(db, current_user)
    return success(data=data.model_dump(by_alias=True), msg="已按从正常到重症排列")


@router.delete("/tasks/{taskId}", summary="撤下一项必做", response_model=None)
def remove_task(
    current_user: CurrentUser,
    db: DbSession,
    taskId: int = Path(..., ge=1),
):
    data = RotationService.remove_task(db, current_user, taskId)
    return success(data=data.model_dump(by_alias=True))


@router.post("/tasks/{taskId}/learn", summary="知识点标记已学", response_model=None)
def learn(
    current_user: CurrentUser,
    db: DbSession,
    taskId: int = Path(..., ge=1),
):
    data = RotationService.learn(db, current_user, taskId)
    return success(data=data.model_dump(by_alias=True))
