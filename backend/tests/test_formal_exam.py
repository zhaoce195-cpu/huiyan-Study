# -*- coding: utf-8 -*-
"""老师组卷的正式考试：指定或抽题、限时、能否回上一题、收卷后才出成绩。"""

from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.db.models  # noqa: F401
from app.db.base import Base
from app.db.models import Role, RoleEnum, TrainingCase, User
from app.schemas.exam import ExamCreate, ExamHandIn
from app.schemas.practice import PracticeSubmitParams
from app.services.exam_service import ExamService
from app.services.practice_service import PracticeService


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
    teacher_role = Role(code=RoleEnum.TEACHER.value, name="教师")
    student_role = Role(code=RoleEnum.STUDENT.value, name="学员")
    db.add_all([teacher_role, student_role])
    db.flush()
    teacher = User(
        username="teacher", password_hash="x", real_name="李老师",
        role_id=teacher_role.id, is_active=True,
    )
    student = User(
        username="student", password_hash="x", real_name="张同学",
        role_id=student_role.id, is_active=True,
    )
    other = User(
        username="other", password_hash="x", real_name="王芳",
        role_id=student_role.id, is_active=True,
    )
    db.add_all([teacher, student, other])
    db.commit()
    return teacher, student, other


def _case(db, teacher, case_no, category="DR", difficulty="EASY"):
    row = TrainingCase(
        case_no=case_no,
        title=case_no,
        category=category,
        difficulty=difficulty,
        gold_dr_grade="2",
        gold_diagnosis="出血",
        is_published=True,
        is_train_case=True,
        archive_status="ACTIVE",
        creator_id=teacher.id,
    )
    db.add(row)
    db.commit()
    return row


def test_teacher_can_pick_cases_in_order(db):
    teacher, _, _ = _people(db)
    first = _case(db, teacher, "T1")
    second = _case(db, teacher, "T2", category="AMD", difficulty="HARD")
    paper = ExamService.create(db, teacher, ExamCreate(
        title="期末",
        duration_minutes=40,
        pass_score=70,
        allow_back=False,
        pick_mode="SELECTED",
        case_ids=[second.id, first.id],
    ))
    assert paper.case_ids == [second.id, first.id]
    assert paper.question_count == 2
    assert paper.duration_minutes == 40
    assert paper.pass_score == 70
    assert paper.allow_back is False


def test_draw_uses_category_and_difficulty(db):
    teacher, _, _ = _people(db)
    easy = _case(db, teacher, "E1", difficulty="EASY")
    _case(db, teacher, "H1", difficulty="HARD")
    _case(db, teacher, "A1", category="AMD", difficulty="EASY")
    paper = ExamService.create(db, teacher, ExamCreate(
        title="抽题",
        pick_mode="DRAW",
        category="DR",
        difficulty="EASY",
        question_count=1,
    ))
    assert paper.case_ids == [easy.id]


def test_draw_refuses_when_there_are_not_enough_cases(db):
    teacher, _, _ = _people(db)
    _case(db, teacher, "E1")
    with pytest.raises(HTTPException) as caught:
        ExamService.create(db, teacher, ExamCreate(
            title="不够",
            pick_mode="DRAW",
            category="DR",
            difficulty="EASY",
            question_count=2,
        ))
    assert caught.value.status_code == 400


def test_answers_stay_hidden_until_the_teacher_collects(db):
    teacher, student, other = _people(db)
    case = _case(db, teacher, "T1")
    paper = ExamService.create(db, teacher, ExamCreate(
        title="小测",
        duration_minutes=30,
        pass_score=100,
        allow_back=False,
        pick_mode="SELECTED",
        case_ids=[case.id],
    ))
    started = ExamService.start(db, student, paper.id)
    PracticeService.submit(db, student, PracticeSubmitParams(
        session_id=started.id,
        student_dr_grade="2",
        student_diagnosis="出血",
        request_id="once",
    ))
    hidden = PracticeService.get_detail(db, student, started.id)
    assert hidden.answers_open is False
    assert hidden.score_total == 0
    ExamService.collect(db, teacher, paper.id)
    opened = PracticeService.get_detail(db, student, started.id)
    assert opened.answers_open is True
    assert opened.score_total > 0
    text = ExamService.csv_text(db, teacher, paper.id)
    assert "张同学" in text
    assert "王芳" in text
    assert "缺考" in text
    assert "不合格" in text


def test_linear_exam_rejects_going_back(db):
    teacher, student, _ = _people(db)
    first = _case(db, teacher, "T1")
    second = _case(db, teacher, "T2")
    paper = ExamService.create(db, teacher, ExamCreate(
        title="不能回",
        allow_back=False,
        pick_mode="SELECTED",
        case_ids=[first.id, second.id],
    ))
    started = ExamService.start(db, student, paper.id)
    second_id = next(item.session_id for item in started.exam_items if item.index == 2)
    with pytest.raises(HTTPException) as caught:
        PracticeService.get_detail(db, student, second_id)
    assert caught.value.status_code == 403
    PracticeService.submit(db, student, PracticeSubmitParams(
        session_id=started.id,
        student_dr_grade="2",
        student_diagnosis="出血",
        request_id="q1",
    ))
    with pytest.raises(HTTPException) as back:
        PracticeService.get_detail(db, student, started.id)
    assert back.value.status_code == 403
    PracticeService.get_detail(db, student, second_id)


def test_allow_back_can_open_the_previous_question(db):
    teacher, student, _ = _people(db)
    first = _case(db, teacher, "T1")
    second = _case(db, teacher, "T2")
    paper = ExamService.create(db, teacher, ExamCreate(
        title="可以回",
        allow_back=True,
        pick_mode="SELECTED",
        case_ids=[first.id, second.id],
    ))
    started = ExamService.start(db, student, paper.id)
    second_id = next(item.session_id for item in started.exam_items if item.index == 2)
    opened = PracticeService.get_detail(db, student, second_id)
    assert opened.id == second_id
    back = PracticeService.get_detail(db, student, started.id)
    assert back.prev_session_id == 0
    assert back.allow_back is True


def test_time_up_collects_the_unfinished_paper(db):
    teacher, student, _ = _people(db)
    case = _case(db, teacher, "T1")
    paper = ExamService.create(db, teacher, ExamCreate(
        title="限时",
        duration_minutes=20,
        allow_back=True,
        pick_mode="SELECTED",
        case_ids=[case.id],
    ))
    started = ExamService.start(db, student, paper.id)
    from app.db.models import PracticeSession
    row = db.query(PracticeSession).filter(PracticeSession.id == started.id).one()
    row.started_at = datetime.now() - timedelta(hours=2)
    db.commit()
    detail = PracticeService.get_detail(db, student, started.id)
    assert detail.status == "SUBMITTED"
    assert detail.answers_open is False
    ExamService.hand_in(db, student, paper.id, ExamHandIn(session_id=started.id, student_dr_grade="2"))
