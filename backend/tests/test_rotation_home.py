# -*- coding: utf-8 -*-
"""学员首页给出轮转进度，且不把病例标题里的分级发下去。"""

import app.db.models  # noqa: F401
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import (
    PracticeSession,
    Role,
    RoleEnum,
    Rotation,
    TrainingCase,
    User,
)
from app.schemas.rotation import TaskCreate
from app.services.rotation_service import RotationService


@pytest.fixture()
def db():
    eng = create_engine("sqlite://")
    Base.metadata.create_all(eng)
    session = sessionmaker(bind=eng)()
    try:
        yield session
    finally:
        session.close()


def _users(db):
    admin_role = Role(code=RoleEnum.ADMIN.value, name="管理员")
    student_role = Role(code=RoleEnum.STUDENT.value, name="学员")
    db.add_all([admin_role, student_role])
    db.flush()
    admin = User(username="admin", password_hash="x", real_name="管理员", role_id=admin_role.id)
    student = User(username="student", password_hash="x", real_name="学员甲", role_id=student_role.id)
    db.add_all([admin, student])
    db.commit()
    return admin, student


def _case(db, admin, title="IDRiD_17 · PDR（NVE）"):
    case = TrainingCase(
        case_no="IDRID-T-IDRiD_17",
        title=title,
        description="",
        category="DR",
        difficulty="HARD",
        patient_name="x",
        patient_gender="U",
        patient_phone="",
        clinical_info="",
        gold_dr_grade="4",
        gold_diagnosis="增殖性",
        teaching_points="",
        pass_score=60,
        is_published=True,
        is_train_case=True,
        creator_id=admin.id,
    )
    db.add(case)
    db.commit()
    return case


def test_student_home_hides_grade_and_tracks_pass(db):
    admin, student = _users(db)
    case = _case(db, admin)
    home = RotationService.home(db, student)
    assert home.role == "student"
    assert home.rotation is not None
    assert home.rotation.pass_score == 60
    assert home.rotation.due_on
    dumped = home.model_dump()
    assert "PDR（NVE）" not in str(dumped)
    case_rows = [row for row in home.tasks if row.kind == "CASE"]
    assert len(case_rows) == 1
    assert case_rows[0].case_no == "IDRID-T-IDRiD_17"
    assert case_rows[0].status == "TODO"
    assert case_rows[0].id in {row.id for row in home.today}

    db.add(PracticeSession(
        user_id=student.id,
        case_id=case.id,
        mode="SELECTED",
        status="SUBMITTED",
        attempt_kind="PRACTICE",
        score_total=82,
        is_passed=1,
    ))
    db.commit()
    again = RotationService.home(db, student)
    done = next(row for row in again.tasks if row.case_id == case.id)
    assert done.status == "DONE"
    assert done.score == 82
    assert done.id not in {row.id for row in again.today}
    assert again.rotation.done >= 1
    assert db.query(Rotation).count() == 1


def test_unfinished_exam_does_not_show_score(db):
    admin, student = _users(db)
    case = _case(db, admin)
    RotationService.home(db, student)
    db.add(PracticeSession(
        user_id=student.id,
        case_id=case.id,
        mode="RANDOM",
        status="SUBMITTED",
        attempt_kind="EXAM",
        exam_group_id="paper-1",
        exam_index=1,
        exam_total=2,
        score_total=90,
        is_passed=1,
    ))
    db.add(PracticeSession(
        user_id=student.id,
        case_id=case.id,
        mode="RANDOM",
        status="DRAFT",
        attempt_kind="EXAM",
        exam_group_id="paper-1",
        exam_index=2,
        exam_total=2,
    ))
    db.commit()
    home = RotationService.home(db, student)
    row = next(item for item in home.tasks if item.case_id == case.id)
    assert row.status == "DOING"
    assert row.score is None


def test_knowledge_mark_and_teacher_progress(db):
    admin, student = _users(db)
    _case(db, admin)
    student_home = RotationService.home(db, student)
    knowledge = next(row for row in student_home.tasks if row.kind == "KNOWLEDGE")
    learned = RotationService.learn(db, student, knowledge.id)
    marked = next(row for row in learned.tasks if row.id == knowledge.id)
    assert marked.status == "LEARNED"

    teacher = RotationService.home(db, admin)
    assert teacher.role == "teacher"
    assert teacher.students[0].name == "学员甲"
    assert teacher.students[0].done == 1
    with pytest.raises(HTTPException) as exc:
        RotationService.add_task(db, student, TaskCreate(kind="KNOWLEDGE", title="不该成功"))
    assert exc.value.status_code == 403
