# -*- coding: utf-8 -*-
"""学员质量评估先进入教师待审核，教师通过后才是已通过。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import Role, RoleEnum, TrainingCase, User
from app.schemas.reading import ReadingListQuery, ReadingReviewParams
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


def _people(db):
    student_role = Role(code=RoleEnum.STUDENT.value, name="学员")
    teacher_role = Role(code=RoleEnum.TEACHER.value, name="教师")
    db.add_all([student_role, teacher_role])
    db.flush()
    student = User(
        username="student", password_hash="x", role_id=student_role.id,
        user_type="student", real_name="学员甲",
    )
    teacher = User(
        username="teacher", password_hash="x", role_id=teacher_role.id,
        user_type="teacher", real_name="带教",
    )
    db.add_all([student, teacher])
    db.flush()
    case = TrainingCase(
        case_no="Q-1", title="质量", category="DR", gold_dr_grade="1",
        is_published=1, is_train_case=1, creator_id=teacher.id,
    )
    db.add(case)
    db.commit()
    return student, teacher, case


def test_student_quality_waits_for_teacher(db):
    student, teacher, case = _people(db)
    sent = ReadingService.submit_quality_review(
        db, student, case.id, "算法建议：优质", {"qualityItems": [{"quality": "good"}]},
    )
    assert sent.status == "SUBMITTED"
    assert sent.record_kind == "QUALITY"

    queued = ReadingService.list_records(
        db, teacher, ReadingListQuery(status="SUBMITTED"),
    )
    assert [row.id for row in queued.list] == [sent.id]
    assert queued.list[0].record_kind == "QUALITY"

    passed = ReadingService.review(
        db, teacher, sent.id, ReadingReviewParams(accept=True, review_comment="图像可用"),
    )
    assert passed.status == "REVIEWED"

    again = ReadingService.submit_quality_review(
        db, student, case.id, "再次评估", {"qualityItems": []},
    )
    assert again.id == sent.id
    assert again.status == "REVIEWED"
