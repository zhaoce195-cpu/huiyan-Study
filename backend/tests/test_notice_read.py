# -*- coding: utf-8 -*-
"""
公告已读状态

原本存在进程内存的字典里，重启即丢失、多副本各存一份。
标记已读的唯一意义就是它下次还在，所以这里守的第一条就是持久化。
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import Notice, NoticeRead, NoticeStatusEnum, Role, RoleEnum, User
from app.schemas.common import NoticeSaveParams
from app.services.notice_service import NoticeService


@pytest.fixture()
def engine():
    eng = create_engine("sqlite://")
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture()
def db(engine):
    s = sessionmaker(bind=engine)()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture()
def seeded(db):
    role = Role(code=RoleEnum.STUDENT.value, name="学员")
    db.add(role)
    db.flush()
    user = User(username="stu", password_hash="x", role_id=role.id)
    other = User(username="stu2", password_hash="x", role_id=role.id)
    db.add_all([user, other])
    db.flush()
    for i in range(3):
        db.add(Notice(
            title=f"公告{i}", content="正文",
            status=NoticeStatusEnum.PUBLISHED.value,
            visible_roles="", publisher_id=user.id,
        ))
    db.commit()
    return user, other


def test_unread_by_default(db, seeded):
    user, _ = seeded
    out = NoticeService.my_notifications(db=db, user=user)
    assert out.total == 3
    assert out.unread == 3


def test_unread_json_exposes_is_read_false(db, seeded):
    user, _ = seeded
    dumped = NoticeService.my_notifications(db=db, user=user).model_dump(by_alias=True)
    item = dumped["list"][0]
    assert item["read"] is False
    assert item["isRead"] is False
    assert dumped["unread"] == 3


def test_republish_clears_reads_so_students_see_it_again(db, seeded):
    """管理员再点发布，必须清掉该条已读，否则学员端永远不再弹窗。"""
    user, _ = seeded
    notice = db.query(Notice).first()
    NoticeService.mark_read(db=db, user=user, ids=[notice.id])
    assert NoticeService.my_notifications(db=db, user=user).unread == 2
    NoticeService.update(
        db,
        notice.id,
        NoticeSaveParams(
            title=notice.title,
            content="更新后再发布",
            status=NoticeStatusEnum.PUBLISHED.value,
            visible_roles=notice.visible_roles,
        ),
    )
    assert db.query(NoticeRead).filter(NoticeRead.notice_id == notice.id).count() == 0
    assert NoticeService.my_notifications(db=db, user=user).unread == 3


def test_listing_does_not_mark_read(db, seeded):
    """拉通知列表不能写成已读，否则学员没点查看就变成已读、登录也不再弹窗。"""
    user, _ = seeded
    NoticeService.my_notifications(db=db, user=user)
    NoticeService.my_notifications(db=db, user=user)
    assert db.query(NoticeRead).count() == 0
    assert NoticeService.my_notifications(db=db, user=user).unread == 3


def test_mark_read_persists(db, seeded):
    user, _ = seeded
    ids = [n.id for n in db.query(Notice).all()]
    NoticeService.mark_read(db=db, user=user, ids=ids[:1])
    out = NoticeService.my_notifications(db=db, user=user)
    assert out.unread == 2


def test_read_state_survives_restart(engine, seeded, db):
    """
    换一个全新的会话再查 —— 等价于后端重启。
    此前状态存在进程字典里，重启后全部回到未读。
    """
    user, _ = seeded
    ids = [n.id for n in db.query(Notice).all()]
    NoticeService.mark_read(db=db, user=user, ids=ids)

    fresh = sessionmaker(bind=engine)()
    try:
        u = fresh.query(User).filter(User.username == "stu").first()
        out = NoticeService.my_notifications(db=fresh, user=u)
        assert out.unread == 0, "重启后已读状态丢失"
    finally:
        fresh.close()


def test_read_state_is_per_user(db, seeded):
    """一个人读过，不能让别人也变成已读"""
    user, other = seeded
    ids = [n.id for n in db.query(Notice).all()]
    NoticeService.mark_read(db=db, user=user, ids=ids)
    assert NoticeService.my_notifications(db=db, user=other).unread == 3


def test_mark_all_read(db, seeded):
    user, _ = seeded
    NoticeService.mark_all_read(db=db, user=user)
    assert NoticeService.my_notifications(db=db, user=user).unread == 0


def test_marking_twice_is_idempotent(db, seeded):
    """
    重复标记不该报错，也不该在关联表里堆重复行 ——
    并发下先查后插会漏，靠唯一约束兜底。
    """
    user, _ = seeded
    ids = [n.id for n in db.query(Notice).all()]
    NoticeService.mark_read(db=db, user=user, ids=ids)
    NoticeService.mark_read(db=db, user=user, ids=ids)
    assert db.query(NoticeRead).filter(NoticeRead.user_id == user.id).count() == len(ids)


def test_first_read_increments_view_count(db, seeded):
    user, other = seeded
    notice = db.query(Notice).first()
    assert notice.view_count == 0
    NoticeService.mark_read(db=db, user=user, ids=[notice.id])
    db.refresh(notice)
    assert notice.view_count == 1
    NoticeService.mark_read(db=db, user=user, ids=[notice.id])
    db.refresh(notice)
    assert notice.view_count == 1, "同一人重复已读不应再加阅读量"
    NoticeService.mark_read(db=db, user=other, ids=[notice.id])
    db.refresh(notice)
    assert notice.view_count == 2


def test_student_only_sees_matching_roles(db, seeded):
    user, _ = seeded
    db.add(Notice(
        title="仅教师", content="教师看",
        status=NoticeStatusEnum.PUBLISHED.value,
        visible_roles="TEACHER,ADMIN", publisher_id=user.id,
    ))
    db.add(Notice(
        title="给学员", content="学员看",
        status=NoticeStatusEnum.PUBLISHED.value,
        visible_roles="STUDENT", publisher_id=user.id,
    ))
    db.commit()
    titles = {it.title for it in NoticeService.my_notifications(db=db, user=user).list}
    assert "给学员" in titles
    assert "仅教师" not in titles


def test_unknown_ids_are_ignored(db, seeded):
    """
    传一个不存在的公告 id 不能在关联表里留下孤儿记录，
    否则未读数会被算错。
    """
    user, _ = seeded
    NoticeService.mark_read(db=db, user=user, ids=[999999])
    assert db.query(NoticeRead).count() == 0
    assert NoticeService.my_notifications(db=db, user=user).unread == 3
