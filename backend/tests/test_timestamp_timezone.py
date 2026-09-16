# -*- coding: utf-8 -*-
"""
时间戳时区（2026-08 用户测试报告 A5）

「入库申请记录 / 公告列表的创建时间比实际操作时间少 8 小时。」

原因是 TimestampMixin 用 server_default=func.now()，在 SQLite 上就是
CURRENT_TIMESTAMP —— 返回 UTC；而各 service 里的业务时间字段（reviewed_at、
published_at 之类）用 Python datetime.now()，是本地时区。同一条记录两套时间源，
列表里两列时间恒差 8 小时。

这里守的是「同源」：ORM 写入的 created_at / updated_at 必须和 datetime.now()
对得上，而不是差出一个时区。
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import Notice, NoticeStatusEnum, Role, RoleEnum, User

# 允许的漂移：只要不是整时区级别的偏差就算对
TOLERANCE = timedelta(minutes=5)


@pytest.fixture()
def db():
    eng = create_engine("sqlite://")
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    try:
        yield s
    finally:
        s.close()


def test_created_at_follows_local_clock(db):
    role = Role(code=RoleEnum.ADMIN.value, name="管理员")
    db.add(role)
    db.commit()

    before = datetime.now()
    assert role.created_at is not None
    assert abs(role.created_at - before) < TOLERANCE, (
        f"created_at={role.created_at} 与本地时间 {before} 相差过大，"
        "多半又退回了数据库侧的 UTC CURRENT_TIMESTAMP"
    )


def test_created_and_updated_are_same_source(db):
    """新建那一刻，两列时间应当基本一致——差 8 小时正是当初的现象"""
    role = Role(code=RoleEnum.ADMIN.value, name="管理员")
    db.add(role)
    db.flush()
    user = User(username="admin", password_hash="x", role_id=role.id)
    db.add(user)
    db.commit()

    assert abs(user.created_at - user.updated_at) < TOLERANCE


def test_updated_at_advances_on_update(db):
    """onupdate 也换成了 Python 侧，确认它仍然会走"""
    role = Role(code=RoleEnum.ADMIN.value, name="管理员")
    db.add(role)
    db.flush()
    publisher = User(username="admin", password_hash="x", role_id=role.id)
    db.add(publisher)
    db.flush()
    notice = Notice(
        title="测试公告",
        content="x",
        status=NoticeStatusEnum.PUBLISHED.value,
        publisher_id=publisher.id,
    )
    db.add(notice)
    db.commit()
    first = notice.updated_at

    notice.title = "改过的标题"
    db.commit()

    assert notice.updated_at >= first
    assert abs(notice.updated_at - datetime.now()) < TOLERANCE
