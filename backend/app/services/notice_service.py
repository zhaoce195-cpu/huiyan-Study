"""
公告 / 通知服务
- 后端只有一张 biz_notice 表，承担两类前端语义：
    a) 后台公告管理（CRUD）
    b) "我的通知"（按 visible_roles 过滤，再叠加用户已读集合）
- 已读集合使用进程内字典存储，重启后丢失。生产可换 Redis：键 user_id:notice_id
"""

import threading
from datetime import datetime
from typing import Dict, List, Optional, Set

from fastapi import HTTPException, status
from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from app.db.models import Notice, NoticeStatusEnum, User
from app.schemas.common import (
    NoticeOut,
    NoticePageOut,
    NoticeSaveParams,
    NotificationItemOut,
    NotificationListOut,
)

# ====================== 已读状态（进程内）======================

_read_lock = threading.Lock()
# user_id → set(notice_id)
_read_set: Dict[int, Set[int]] = {}


def _read_get(user_id: int) -> Set[int]:
    with _read_lock:
        return set(_read_set.get(user_id, set()))


def _read_mark(user_id: int, ids: List[int]) -> None:
    if not ids:
        return
    with _read_lock:
        s = _read_set.setdefault(user_id, set())
        for i in ids:
            s.add(int(i))


def _read_mark_all(user_id: int, ids: List[int]) -> None:
    with _read_lock:
        _read_set[user_id] = set(int(i) for i in ids)


# ====================== 工具 ======================

def _to_notice_out(n: Notice) -> NoticeOut:
    publisher_name = ""
    if n.publisher:
        publisher_name = n.publisher.real_name or n.publisher.username or ""
    return NoticeOut(
        id=n.id,
        title=n.title,
        summary=n.summary or "",
        content=n.content or "",
        cover_url=n.cover_url or "",
        notice_type=n.notice_type,
        status=n.status,
        visible_roles=n.visible_roles or "",
        is_top=bool(n.is_top),
        publisher_id=n.publisher_id or 0,
        publisher_name=publisher_name,
        publish_at=n.publish_at.strftime("%Y-%m-%d %H:%M:%S") if n.publish_at else None,
        expire_at=n.expire_at.strftime("%Y-%m-%d %H:%M:%S") if n.expire_at else None,
        view_count=n.view_count or 0,
        created_at=n.created_at.strftime("%Y-%m-%d %H:%M:%S") if n.created_at else "",
        updated_at=n.updated_at.strftime("%Y-%m-%d %H:%M:%S") if n.updated_at else "",
    )


def _notice_to_notification(n: Notice) -> NotificationItemOut:
    """公告 → 通知中心 item（前端的 type 是小写）"""
    type_map = {
        "SYSTEM": "system",
        "SCREENING": "screening",
        "TRAINING": "training",
        "EXAM": "training",
    }
    return NotificationItemOut(
        id=n.id,
        type=type_map.get(n.notice_type, "system"),  # type: ignore[arg-type]
        title=n.title,
        content=n.summary or n.content[:120],
        read=False,  # 由调用者根据 read_set 覆盖
        created_at=(n.publish_at or n.created_at).strftime("%Y-%m-%d %H:%M:%S") if (n.publish_at or n.created_at) else "",
    )


# ====================== Service ======================

class NoticeService:

    # ---------- 公告管理（CRUD） ----------

    @staticmethod
    def create(db: Session, user: User, params: NoticeSaveParams) -> NoticeOut:
        n = Notice(
            title=params.title,
            summary=params.summary or "",
            content=params.content,
            cover_url=params.cover_url or "",
            notice_type=params.notice_type or "SYSTEM",
            status=params.status or NoticeStatusEnum.DRAFT.value,
            visible_roles=params.visible_roles or "",
            is_top=bool(params.is_top),
            publisher_id=user.id,
            publish_at=_parse_dt(params.publish_at),
            expire_at=_parse_dt(params.expire_at),
        )
        if n.status == NoticeStatusEnum.PUBLISHED.value and n.publish_at is None:
            n.publish_at = datetime.now()
        db.add(n)
        db.commit()
        db.refresh(n)
        return _to_notice_out(n)

    @staticmethod
    def update(db: Session, notice_id: int, params: NoticeSaveParams) -> NoticeOut:
        n = db.query(Notice).filter(Notice.id == notice_id).first()
        if not n:
            raise HTTPException(404, detail=f"公告不存在：{notice_id}")
        n.title = params.title
        n.summary = params.summary or ""
        n.content = params.content
        n.cover_url = params.cover_url or ""
        n.notice_type = params.notice_type or n.notice_type
        n.status = params.status or n.status
        n.visible_roles = params.visible_roles or ""
        n.is_top = bool(params.is_top)
        if params.publish_at is not None:
            n.publish_at = _parse_dt(params.publish_at)
        if params.expire_at is not None:
            n.expire_at = _parse_dt(params.expire_at)
        if n.status == NoticeStatusEnum.PUBLISHED.value and n.publish_at is None:
            n.publish_at = datetime.now()
        db.commit()
        db.refresh(n)
        return _to_notice_out(n)

    @staticmethod
    def delete(db: Session, notice_id: int) -> None:
        n = db.query(Notice).filter(Notice.id == notice_id).first()
        if not n:
            raise HTTPException(404, detail=f"公告不存在：{notice_id}")
        db.delete(n)
        db.commit()

    @staticmethod
    def list(
        db: Session,
        keyword: Optional[str] = None,
        notice_type: Optional[str] = None,
        status_filter: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> NoticePageOut:
        q = db.query(Notice)
        if keyword:
            kw = f"%{keyword.strip()}%"
            q = q.filter(or_(Notice.title.like(kw), Notice.summary.like(kw)))
        if notice_type:
            q = q.filter(Notice.notice_type == notice_type)
        if status_filter:
            q = q.filter(Notice.status == status_filter)

        total = q.count()
        rows: List[Notice] = (
            q.order_by(desc(Notice.is_top), desc(Notice.id))
            .offset(max(0, (page - 1) * page_size))
            .limit(page_size)
            .all()
        )
        return NoticePageOut(
            total=total,
            page=page,
            page_size=page_size,
            list=[_to_notice_out(n) for n in rows],
        )

    @staticmethod
    def detail(db: Session, notice_id: int) -> NoticeOut:
        n = db.query(Notice).filter(Notice.id == notice_id).first()
        if not n:
            raise HTTPException(404, detail=f"公告不存在：{notice_id}")
        # 阅读量 +1
        n.view_count = (n.view_count or 0) + 1
        db.commit()
        db.refresh(n)
        return _to_notice_out(n)

    # ---------- 通知中心 ----------

    @staticmethod
    def my_notifications(
        db: Session,
        user: User,
        page: int = 1,
        page_size: int = 20,
    ) -> NotificationListOut:
        role_code = user.role.code if user.role else ""

        q = db.query(Notice).filter(Notice.status == NoticeStatusEnum.PUBLISHED.value)
        # 可见角色：空字符串=全员；否则要包含当前角色
        q = q.filter(or_(
            Notice.visible_roles == "",
            Notice.visible_roles.like(f"%{role_code}%"),
        ))
        # 时间窗口：未配置 expire_at 的视为永久
        now = datetime.now()
        q = q.filter(or_(Notice.expire_at.is_(None), Notice.expire_at >= now))
        q = q.filter(or_(Notice.publish_at.is_(None), Notice.publish_at <= now))

        total = q.count()
        rows: List[Notice] = (
            q.order_by(desc(Notice.is_top), desc(Notice.publish_at), desc(Notice.id))
            .offset(max(0, (page - 1) * page_size))
            .limit(page_size)
            .all()
        )

        read_ids = _read_get(user.id)
        items: List[NotificationItemOut] = []
        unread = 0
        for r in rows:
            it = _notice_to_notification(r)
            it.read = r.id in read_ids
            if not it.read:
                unread += 1
            items.append(it)

        return NotificationListOut(total=total, unread=unread, list=items)

    @staticmethod
    def mark_read(db: Session, user: User, ids: List[int]) -> None:
        if not ids:
            return
        # 仅对存在的公告打标，避免任意整数都进 set
        existing_ids = [
            r.id for r in db.query(Notice.id).filter(Notice.id.in_(ids)).all()
        ]
        _read_mark(user.id, existing_ids)

    @staticmethod
    def mark_all_read(db: Session, user: User) -> None:
        all_ids = [
            r.id for r in db.query(Notice.id)
            .filter(Notice.status == NoticeStatusEnum.PUBLISHED.value).all()
        ]
        _read_mark_all(user.id, all_ids)


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace(" ", "T"))
    except ValueError:
        return None
