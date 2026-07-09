"""
用户站内消息路由（per-user）
- GET  /user-messages                列表（自己的消息）
- GET  /user-messages/unread-count   未读数
- POST /user-messages/{id}/read      标某条已读
- POST /user-messages/read-all       全部标已读
"""

from typing import Optional

from fastapi import APIRouter, Depends, Path, Query

from app.common.response import success
from app.core.dependencies import CurrentUser, DbSession, get_current_user
from app.schemas.organization import UserMessageReadParams
from app.services.user_message_service import UserMessageService


router = APIRouter(
    prefix="/user-messages",
    tags=["11. 用户消息"],
)


any_login = Depends(get_current_user)


@router.get(
    "",
    summary="我的站内消息列表",
    response_model=None,
    dependencies=[any_login],
)
def list_my_messages(
    current_user: CurrentUser,
    db: DbSession,
    type: Optional[str] = Query(None, description="可选筛选类型：org_application/system"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
):
    out = UserMessageService.list_my(
        db,
        user_id=current_user.id,
        msg_type=type,
        page=page,
        page_size=pageSize,
    )
    return success(data=out.model_dump(by_alias=True))


@router.get(
    "/unread-count",
    summary="我的未读消息数",
    response_model=None,
    dependencies=[any_login],
)
def my_unread_count(
    current_user: CurrentUser,
    db: DbSession,
):
    cnt = UserMessageService.unread_count(db, user_id=current_user.id)
    return success(data={"unread": cnt})


@router.post(
    "/{msgId}/read",
    summary="标记单条消息已读",
    response_model=None,
    dependencies=[any_login],
)
def mark_one_read(
    current_user: CurrentUser,
    db: DbSession,
    msgId: int = Path(..., ge=1),
):
    UserMessageService.assert_owner(db, user_id=current_user.id, msg_id=msgId)
    UserMessageService.mark_read(db, user_id=current_user.id, ids=[msgId])
    return success(msg="已标记为已读")


@router.post(
    "/read",
    summary="批量标记已读",
    response_model=None,
    dependencies=[any_login],
)
def mark_batch_read(
    params: UserMessageReadParams,
    current_user: CurrentUser,
    db: DbSession,
):
    n = UserMessageService.mark_read(db, user_id=current_user.id, ids=params.ids or [])
    return success(data={"updated": n})


@router.post(
    "/read-all",
    summary="全部标记已读",
    response_model=None,
    dependencies=[any_login],
)
def mark_all(
    current_user: CurrentUser,
    db: DbSession,
):
    n = UserMessageService.mark_all_read(db, user_id=current_user.id)
    return success(data={"updated": n}, msg="已全部标为已读")
