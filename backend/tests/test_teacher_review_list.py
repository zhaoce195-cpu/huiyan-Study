# -*- coding: utf-8 -*-
"""
教师质量评估 / 待审核列表必须能看到学员已提交的记录。

第三轮测试：阅片工作台 → 质量评估，实际看不到 student 的待审核作业。
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import (
    PracticeSession,
    PracticeStatusEnum,
    Role,
    RoleEnum,
    TrainingCase,
    User,
)
from app.schemas.practice import PracticeListQuery
from app.schemas.reading import ReadingListQuery, ReadingSaveParams
from app.services.practice_service import PracticeService
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
def seeded(db):
    srole = Role(code=RoleEnum.STUDENT.value, name="学员")
    trole = Role(code=RoleEnum.TEACHER.value, name="教师")
    db.add_all([srole, trole])
    db.flush()
    student = User(
        username="student",
        password_hash="x",
        role_id=srole.id,
        user_type="student",
        real_name="学员甲",
    )
    teacher = User(
        username="teacher",
        password_hash="x",
        role_id=trole.id,
        user_type="teacher",
        real_name="带教",
    )
    other = User(
        username="stu2",
        password_hash="x",
        role_id=srole.id,
        user_type="student",
        real_name="学员乙",
    )
    db.add_all([student, teacher, other])
    db.flush()
    case = TrainingCase(
        case_no="R-QA-001",
        title="质量评估用例",
        category="DR",
        gold_dr_grade="2",
        is_published=1,
        is_train_case=1,
        creator_id=teacher.id,
    )
    db.add(case)
    db.commit()
    return {"student": student, "teacher": teacher, "other": other, "case": case}


def _submit_reading(case_id, request_id="qa-1"):
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
        submit=True,
        request_id=request_id,
    )


def test_teacher_sees_student_submitted_reading(db, seeded):
    student, teacher, case = seeded["student"], seeded["teacher"], seeded["case"]
    ReadingService.save(db, student, _submit_reading(case.id))

    page = ReadingService.list_records(
        db, teacher, ReadingListQuery(status="SUBMITTED")
    )
    assert page.total >= 1
    assert any(row.user_id == student.id and row.status == "SUBMITTED" for row in page.list)
    assert any(row.user_name == "学员甲" for row in page.list)


def test_student_list_does_not_include_other_students(db, seeded):
    student, other, case = seeded["student"], seeded["other"], seeded["case"]
    ReadingService.save(db, student, _submit_reading(case.id, "qa-stu"))
    ReadingService.save(db, other, _submit_reading(case.id, "qa-other"))

    page = ReadingService.list_records(
        db, student, ReadingListQuery(status="SUBMITTED")
    )
    assert all(row.user_id == student.id for row in page.list)
    assert not any(row.user_id == other.id for row in page.list)


def test_teacher_review_moves_submitted_to_reviewed(db, seeded):
    from app.schemas.reading import ReadingReviewParams

    student, teacher, case = seeded["student"], seeded["teacher"], seeded["case"]
    out = ReadingService.save(db, student, _submit_reading(case.id, "qa-grade"))
    assert out.status == "SUBMITTED"

    reviewed = ReadingService.review(
        db,
        teacher,
        out.id,
        ReadingReviewParams(review_comment="病灶定位准确", accept=True),
    )
    assert reviewed.status == "REVIEWED"
    assert reviewed.review_comment == "病灶定位准确"

    pending = ReadingService.list_records(
        db, teacher, ReadingListQuery(status="SUBMITTED")
    )
    assert not any(row.id == out.id for row in pending.list)

    done = ReadingService.list_records(
        db, teacher, ReadingListQuery(status="REVIEWED")
    )
    assert any(row.id == out.id for row in done.list)


def test_review_one_record_does_not_change_another(db, seeded):
    from app.schemas.reading import ReadingReviewParams

    student, other, teacher, case = (
        seeded["student"],
        seeded["other"],
        seeded["teacher"],
        seeded["case"],
    )
    a = ReadingService.save(db, student, _submit_reading(case.id, "iso-a"))
    b = ReadingService.save(db, other, _submit_reading(case.id, "iso-b"))
    assert a.id != b.id
    assert a.status == b.status == "SUBMITTED"

    ReadingService.review(
        db, teacher, a.id, ReadingReviewParams(review_comment="只评第一条", accept=True)
    )
    left = ReadingService.get_detail(db, teacher, b.id)
    assert left.status == "SUBMITTED"
    assert left.review_comment == ""

    done = ReadingService.get_detail(db, teacher, a.id)
    assert done.status == "REVIEWED"


def test_teacher_sees_student_submitted_practice(db, seeded):
    student, teacher, case = seeded["student"], seeded["teacher"], seeded["case"]
    rec = PracticeSession(
        user_id=student.id,
        case_id=case.id,
        status=PracticeStatusEnum.SUBMITTED.value,
    )
    db.add(rec)
    db.commit()

    page = PracticeService.list_records(
        db, teacher, PracticeListQuery(status="SUBMITTED")
    )
    assert page.total >= 1
    assert any(row.user_id == student.id for row in page.list)
