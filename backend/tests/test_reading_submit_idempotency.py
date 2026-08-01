# -*- coding: utf-8 -*-
"""
阅片提交的幂等

草稿保存复用同用户+同病例+同影像的最近一条草稿，本身是 upsert，天然幂等。
问题出在提交：记录被置为 SUBMITTED 之后，断网重试的那次请求
再去找草稿就找不到了，于是新建一条并再次提交 ——
同一份阅片凭空变成两条记录，教师端会看到重复待审。
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import (
    ReadingAnnotation,
    ReadingStatusEnum,
    Role,
    RoleEnum,
    TrainingCase,
    User,
)
from app.schemas.reading import ReadingSaveParams
from app.services.reading_service import ReadingService


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def ctx(db):
    role = Role(code=RoleEnum.STUDENT.value, name="学员")
    db.add(role)
    db.flush()
    user = User(username="stu", password_hash="x", role_id=role.id)
    db.add(user)
    db.flush()
    case = TrainingCase(case_no="R-001", title="阅片", category="DR",
                        gold_dr_grade="2", is_published=1, is_train_case=1,
                        creator_id=user.id)
    db.add(case)
    db.commit()
    return user, case


def _params(case_id, request_id="", submit=True, note=""):
    return ReadingSaveParams(
        case_id=case_id,
        image_index=0,
        image_url="/static/a.jpg",
        diagnosis={
            "readability": "readable",
            "dr_grade": "2",
            "confidence": "high",
            "disposition": "followup_6m",
        },
        note=note,
        submit=submit,
        request_id=request_id,
    )


def test_retry_with_same_key_does_not_create_a_second_record(db, ctx):
    user, case = ctx
    first = ReadingService.save(db, user, _params(case.id, "req-1"))
    again = ReadingService.save(db, user, _params(case.id, "req-1"))

    assert again.id == first.id
    assert db.query(ReadingAnnotation).count() == 1


def test_retry_returns_the_original_record(db, ctx):
    """重试是回放，不是重存：第二次带来的改动不应生效"""
    user, case = ctx
    first = ReadingService.save(db, user, _params(case.id, "req-1", note="原始结论"))
    again = ReadingService.save(db, user, _params(case.id, "req-1", note="改过的结论"))

    assert again.note == first.note == "原始结论"


def test_submit_is_recorded_with_its_key(db, ctx):
    user, case = ctx
    ReadingService.save(db, user, _params(case.id, "req-1"))
    row = db.query(ReadingAnnotation).first()
    assert row.submit_request_id == "req-1"
    assert row.status == ReadingStatusEnum.SUBMITTED.value


def test_draft_save_does_not_consume_the_key(db, ctx):
    """
    草稿不是提交，不该占用幂等键 ——
    否则学员存过草稿后，真正提交时会被当成重试直接回放，提交不上去。
    """
    user, case = ctx
    ReadingService.save(db, user, _params(case.id, "req-1", submit=False))
    row = db.query(ReadingAnnotation).first()
    assert row.submit_request_id is None
    assert row.status == ReadingStatusEnum.DRAFT.value

    out = ReadingService.save(db, user, _params(case.id, "req-1", submit=True))
    assert out.status == ReadingStatusEnum.SUBMITTED.value


def test_a_new_reading_pass_uses_a_new_key(db, ctx):
    """
    换一个键表示这是新的一次阅片。原有「可多次阅片」的策略不变，
    幂等只负责认出重试，不顺手改掉业务规则。
    """
    user, case = ctx
    first = ReadingService.save(db, user, _params(case.id, "req-1"))
    second = ReadingService.save(db, user, _params(case.id, "req-2"))

    assert second.id != first.id
    assert db.query(ReadingAnnotation).count() == 2


def test_without_key_old_behaviour_is_unchanged(db, ctx):
    """旧客户端不带键：维持原状，每次提交新建一条"""
    user, case = ctx
    ReadingService.save(db, user, _params(case.id))
    ReadingService.save(db, user, _params(case.id))
    assert db.query(ReadingAnnotation).count() == 2
