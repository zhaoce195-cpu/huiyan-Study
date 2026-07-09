"""
用户站内消息业务层
- 仅由 OrganizationService.review() 在事务内调用 push() 推送
- list_my / mark_read / mark_all 给前端「我的消息」消费
"""

from datetime import datetime
from typing import List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.db.models import UserMessage, MessageTypeEnum
from app.schemas.organization import UserMessageOut, UserMessagePage


def _to_out(msg: UserMessage) -> UserMessageOut:
    return UserMessageOut(
        id=msg.id,
        type=msg.type,
        title=msg.title,
        content=msg.content,
        ref_type=msg.ref_type or "",
        ref_id=msg.ref_id,
        is_read=msg.is_read,
        read_at=msg.read_at,
        created_at=msg.created_at,
    )


class UserMessageService:

    @staticmethod
    def push(
        db: Session,
        *,
        user_id: int,
        msg_type: str,
        title: str,
        content: str,
        ref_type: str = "",
        ref_id: Optional[int] = None,
        commit: bool = False,
    ) -> UserMessage:
        """
        创建一条 per-user 消息。
        commit=False 时由调用方统一提交（适合在 review 同事务里 push）；
        commit=True 时立即提交。
        """
        msg = UserMessage(
            user_id=user_id,
            type=msg_type,
            title=title or "",
            content=content or "",
            ref_type=ref_type or "",
            ref_id=ref_id,
            is_read=False,
            created_at=datetime.now(),
        )
        db.add(msg)
        if commit:
            db.commit()
            db.refresh(msg)
        else:
            db.flush()
        return msg

    @staticmethod
    def list_my(
        db: Session,
        *,
        user_id: int,
        msg_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> UserMessagePage:
        q = db.query(UserMessage).filter(UserMessage.user_id == user_id)
        if msg_type:
            q = q.filter(UserMessage.type == msg_type)

        total = q.count()
        unread = (
            db.query(UserMessage)
            .filter(UserMessage.user_id == user_id, UserMessage.is_read == False)  # noqa: E712
            .count()
        )

        rows: List[UserMessage] = (
            q.order_by(desc(UserMessage.id))
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return UserMessagePage(
            total=total,
            unread=unread,
            page=page,
            page_size=page_size,
            list=[_to_out(m) for m in rows],
        )

    @staticmethod
    def unread_count(db: Session, *, user_id: int) -> int:
        return (
            db.query(UserMessage)
            .filter(UserMessage.user_id == user_id, UserMessage.is_read == False)  # noqa: E712
            .count()
        )

    @staticmethod
    def mark_read(db: Session, *, user_id: int, ids: List[int]) -> int:
        if not ids:
            return 0
        rows = (
            db.query(UserMessage)
            .filter(
                UserMessage.user_id == user_id,
                UserMessage.id.in_(ids),
                UserMessage.is_read == False,  # noqa: E712
            )
            .all()
        )
        now = datetime.now()
        for m in rows:
            m.is_read = True
            m.read_at = now
        db.commit()
        return len(rows)

    @staticmethod
    def mark_all_read(db: Session, *, user_id: int) -> int:
        rows = (
            db.query(UserMessage)
            .filter(
                UserMessage.user_id == user_id,
                UserMessage.is_read == False,  # noqa: E712
            )
            .all()
        )
        now = datetime.now()
        for m in rows:
            m.is_read = True
            m.read_at = now
        db.commit()
        return len(rows)

    @staticmethod
    def assert_owner(db: Session, *, user_id: int, msg_id: int) -> UserMessage:
        msg = db.query(UserMessage).filter(UserMessage.id == msg_id).first()
        if not msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"消息不存在：{msg_id}",
            )
        if msg.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权操作他人消息",
            )
        return msg
