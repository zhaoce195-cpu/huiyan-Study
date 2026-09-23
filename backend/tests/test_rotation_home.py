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
from app.schemas.rotation import StudentGroupUpdate, TaskCreate, TaskOrder
from app.services.case_browse_service import CaseBrowseService
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
    assert home.study_year == "未分组"
    student.study_year = "2024级"
    student.rotation_batch = "2026年上半年"
    db.commit()
    home = RotationService.home(db, student)
    assert home.study_year == "2024级"
    assert home.rotation_batch == "2026年上半年"
    assert home.mentor_group == "未分组"
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
    learned_snap = next(
        item for item in teacher.students[0].tasks if item.task_id == knowledge.id
    )
    assert learned_snap.status == "LEARNED"
    with pytest.raises(HTTPException) as exc:
        RotationService.add_task(db, student, TaskCreate(kind="KNOWLEDGE", title="不该成功"))
    assert exc.value.status_code == 403


def test_leave_training_writes_case_and_drops_task(db):
    admin, student = _users(db)
    case = _case(db, admin)
    before = RotationService.home(db, student)
    assert any(row.case_id == case.id for row in before.tasks)

    detail = CaseBrowseService.remove_from_training(db, admin, case.id)
    assert detail.is_train_case is False
    db.refresh(case)
    assert case.is_train_case is False

    after = RotationService.home(db, student)
    assert all(row.case_id != case.id for row in after.tasks)

    joined = CaseBrowseService.join_training(db, admin, case.id)
    assert joined.is_train_case is True
    db.refresh(case)
    assert case.is_train_case is True


def test_groups_keep_completion_and_problems_apart(db):
    admin, student = _users(db)
    other = User(
        username="student2",
        password_hash="x",
        real_name="学员乙",
        role_id=student.role_id,
        study_year="2025级",
        rotation_batch="2026秋",
        mentor_group="眼底二组",
    )
    student.study_year = "2024级"
    student.rotation_batch = "2026春"
    student.mentor_group = "眼底一组"
    db.add(other)
    db.commit()
    case = _case(db, admin)
    RotationService.home(db, student)
    db.add(PracticeSession(
        user_id=student.id,
        case_id=case.id,
        mode="SELECTED",
        status="SUBMITTED",
        attempt_kind="PRACTICE",
        error_points=[{"label": "微动脉瘤", "type": "missed"}],
    ))
    db.commit()

    home = RotationService.home(db, admin)
    by_year = {row.study_year: row for row in home.groups}
    assert set(by_year) == {"2024级", "2025级"}
    assert by_year["2024级"].weak_labels[0].label == "微动脉瘤"
    assert by_year["2024级"].weak_labels[0].missed == 1
    assert by_year["2025级"].weak_labels == []
    assert by_year["2024级"].student_count == 1
    by_name = {row.name: row.username for row in home.students}
    assert by_name["学员甲"] == "student"

    moved = RotationService.set_student_group(
        db,
        admin,
        other.id,
        StudentGroupUpdate(study_year="2024级", rotation_batch="2026春", mentor_group="眼底一组"),
    )
    assert len(moved.groups) == 1
    assert moved.groups[0].student_count == 2
    assert moved.groups[0].study_year == "2024级"


def test_recommend_by_year_or_group_and_keep_order(db):
    admin, student = _users(db)
    other = User(
        username="student2",
        password_hash="x",
        real_name="学员乙",
        role_id=student.role_id,
        study_year="2025级",
        mentor_group="眼底二组",
    )
    student.study_year = "2024级"
    student.mentor_group = "眼底一组"
    db.add(other)
    db.add(Rotation(
        title="测试轮转",
        start_on="2026-09-01",
        due_on="2026-10-20",
        pass_score=60,
        status="ACTIVE",
        creator_id=admin.id,
    ))
    db.commit()
    mild = _case(db, admin, title="轻度 · DR 1 级")
    mild.case_no = "T-MILD"
    mild.gold_dr_grade = "1"
    severe = _case(db, admin, title="重度 · DR 3 级")
    severe.case_no = "T-SEVERE"
    severe.gold_dr_grade = "3"
    db.commit()

    RotationService.add_task(
        db, admin,
        TaskCreate(kind="CASE", case_id=severe.id, tier="REQUIRED", scope="YEAR", scope_value="2024级"),
    )
    home = RotationService.add_task(
        db, admin,
        TaskCreate(kind="CASE", case_id=mild.id, tier="EXTENSION", scope="GROUP", scope_value="眼底一组"),
    )
    assert [row.kind_text for row in home.tasks if row.case_id in (mild.id, severe.id)] == ["必做病例", "拓展病例"]
    year_row = next(row for row in home.tasks if row.case_id == severe.id)
    assert year_row.scope_text == "2024级"
    assert year_row.student_count == 1

    student_home = RotationService.home(db, student)
    assert any(row.case_id == severe.id and row.tier == "REQUIRED" for row in student_home.tasks)
    assert any(row.case_id == mild.id and row.tier == "EXTENSION" for row in student_home.tasks)
    assert student_home.rotation.total == sum(1 for row in student_home.tasks if row.tier != "EXTENSION")
    assert "DR 3" not in str(student_home.model_dump())
    assert "DR 1" not in str(student_home.model_dump())

    other_home = RotationService.home(db, other)
    assert all(row.case_id != severe.id for row in other_home.tasks)
    assert all(row.case_id != mild.id for row in other_home.tasks)

    arranged = RotationService.arrange(db, admin)
    case_rows = [row for row in arranged.tasks if row.kind == "CASE" and row.case_id in (mild.id, severe.id)]
    assert [row.case_id for row in case_rows] == [severe.id, mild.id]
    flipped = RotationService.reorder(db, admin, TaskOrder(
        task_ids=[case_rows[1].id, case_rows[0].id],
    ))
    again = [row.case_id for row in flipped.tasks if row.case_id in (mild.id, severe.id)]
    assert again[0] == mild.id
