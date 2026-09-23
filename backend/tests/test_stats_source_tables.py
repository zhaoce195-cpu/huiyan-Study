# -*- coding: utf-8 -*-
"""
统计口径读的是真正在写的表（2026-08 用户测试报告 D-1）

「学员页面显示已有练习和提交记录，但管理页面显示完成病例为 0。」

根因：study_hours / training_overview 聚合 TrainingRecord，而那张表没有任何
活跃写入方（training_service 里写它的两个端点前端从不调用），线上是空表。
学员的真实提交落在 PracticeSession（自主练习）和 ReadingAnnotation（阅片工作台）。

这里守的是：只要学员交过东西，管理端就必须数得出来——而不是恒为 0。
"""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import (
    PracticeSession,
    PracticeStatusEnum,
    ReadingAnnotation,
    ReadingStatusEnum,
    Role,
    RoleEnum,
    TrainingCase,
    User,
)
from app.services.common_service import CommonService


@pytest.fixture()
def db():
    eng = create_engine("sqlite://")
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture()
def seeded(db):
    role = Role(code=RoleEnum.STUDENT.value, name="学员")
    db.add(role)
    db.flush()
    student = User(username="stu", password_hash="x", role_id=role.id, is_active=True)
    db.add(student)
    db.flush()

    cases = []
    for i in range(3):
        c = TrainingCase(
            case_no=f"T{i}", case_sn=f"CASE{i}", title=f"病例{i}",
            category="DR", difficulty="MEDIUM", patient_name="教学病例",
            patient_gender="U", patient_phone="", is_published=True,
            gold_dr_grade="2", creator_id=student.id,
        )
        db.add(c)
        cases.append(c)
    db.flush()
    db.commit()
    return {"student": student, "cases": cases}


def _practice(user, case, status, **kw):
    return PracticeSession(
        user_id=user.id, case_id=case.id, mode="SELECTED", status=status,
        submitted_at=datetime.now() if status != PracticeStatusEnum.DRAFT.value else None,
        **kw,
    )


def test_practice_submissions_are_counted(db, seeded):
    """报告里的原始场景：学员交过练习，管理端不该显示 0"""
    stu, cases = seeded["student"], seeded["cases"]
    db.add(_practice(stu, cases[0], PracticeStatusEnum.SUBMITTED.value,
                     duration_seconds=600, iou_avg=0.5, is_passed=True))
    db.add(_practice(stu, cases[1], PracticeStatusEnum.SUBMITTED.value,
                     duration_seconds=1200, iou_avg=0.3, is_passed=False))
    db.commit()

    item = CommonService.study_hours(db).list[0]
    assert item.case_count == 2
    assert item.total_seconds == 1800
    assert item.total_hours == 0.5
    assert item.avg_iou == pytest.approx(0.4, abs=1e-3)


def test_draft_practice_not_counted(db, seeded):
    """草稿是「还没交」，不能算完成"""
    stu, cases = seeded["student"], seeded["cases"]
    db.add(_practice(stu, cases[0], PracticeStatusEnum.DRAFT.value, duration_seconds=999))
    db.commit()

    item = CommonService.study_hours(db).list[0]
    assert item.case_count == 0
    assert item.total_seconds == 0


def test_reading_submissions_also_counted(db, seeded):
    """阅片工作台交的也算完成病例，否则又会漏掉一批"""
    stu, cases = seeded["student"], seeded["cases"]
    db.add(ReadingAnnotation(
        user_id=stu.id, case_id=cases[2].id, image_index=0, image_url="/x.jpg",
        status=ReadingStatusEnum.SUBMITTED.value,
    ))
    db.commit()

    assert CommonService.study_hours(db).list[0].case_count == 1


def test_same_case_practiced_and_read_counts_once(db, seeded):
    """同一份病例既练过又阅过，只能算一例"""
    stu, cases = seeded["student"], seeded["cases"]
    db.add(_practice(stu, cases[0], PracticeStatusEnum.SUBMITTED.value, duration_seconds=60))
    db.add(ReadingAnnotation(
        user_id=stu.id, case_id=cases[0].id, image_index=0, image_url="/x.jpg",
        status=ReadingStatusEnum.SUBMITTED.value,
    ))
    db.commit()

    assert CommonService.study_hours(db).list[0].case_count == 1


def test_repeat_attempts_on_one_case_count_once(db, seeded):
    """同一病例练了三遍还是一例，但学时要累加"""
    stu, cases = seeded["student"], seeded["cases"]
    for _ in range(3):
        db.add(_practice(stu, cases[0], PracticeStatusEnum.SUBMITTED.value,
                         duration_seconds=100))
    db.commit()

    item = CommonService.study_hours(db).list[0]
    assert item.case_count == 1
    assert item.total_seconds == 300


def test_overview_reflects_real_submissions(db, seeded):
    """全院总览的提交数 / 通过率同样不能恒为 0"""
    stu, cases = seeded["student"], seeded["cases"]
    db.add(_practice(stu, cases[0], PracticeStatusEnum.SUBMITTED.value,
                     duration_seconds=60, iou_avg=0.8, is_passed=True))
    db.add(_practice(stu, cases[1], PracticeStatusEnum.SUBMITTED.value,
                     duration_seconds=60, iou_avg=0.2, is_passed=False))
    db.add(ReadingAnnotation(
        user_id=stu.id, case_id=cases[2].id, image_index=0, image_url="/x.jpg",
        status=ReadingStatusEnum.SUBMITTED.value,
    ))
    db.commit()

    ov = CommonService.training_overview(db)
    assert ov.total_records == 3          # 2 练习 + 1 阅片
    assert ov.avg_iou == pytest.approx(0.5, abs=1e-3)
    # 通过率的分母只能是练习提交数：阅片没有「是否通过」这回事
    assert ov.pass_rate == pytest.approx(0.5, abs=1e-4)


def test_student_teacher_and_admin_share_one_count(db, seeded, monkeypatch):
    """练习次数、完成病例、平均成绩、学时在三个角色上是同一套数。草稿不计入。"""
    from app.services.practice_service import PracticeService, _to_out
    from app.services.training_service import TrainingService

    stu, cases = seeded["student"], seeded["cases"]
    db.add(_practice(
        stu, cases[0], PracticeStatusEnum.SUBMITTED.value,
        duration_seconds=600, score_total=80, iou_avg=0.5, is_passed=True,
    ))
    db.add(_practice(
        stu, cases[0], PracticeStatusEnum.DRAFT.value, duration_seconds=999, score_total=10,
    ))
    db.add(ReadingAnnotation(
        user_id=stu.id, case_id=cases[1].id, image_index=0, image_url="/x.jpg",
        status=ReadingStatusEnum.SUBMITTED.value,
    ))
    teacher_role = Role(code=RoleEnum.TEACHER.value, name="教师")
    db.add(teacher_role)
    db.flush()
    teacher = User(username="tea", password_hash="x", role_id=teacher_role.id, is_active=True)
    db.add(teacher)
    db.commit()

    item = CommonService.study_hours(db).list[0]
    stats = PracticeService.stats(db, stu)
    train = TrainingService.stats(db, stu)
    assert item.practice_count == stats.submitted_sessions == 1
    assert item.case_count == stats.completed_cases == train.done_cases == 2
    assert item.avg_score == stats.avg_score == 80
    assert item.total_seconds == stats.total_duration == train.total_duration == 600

    locked = _practice(
        stu, cases[2], PracticeStatusEnum.SUBMITTED.value,
        duration_seconds=30, score_total=66, attempt_kind="EXAM",
    )
    db.add(locked)
    db.commit()
    db.refresh(locked)
    monkeypatch.setattr(
        "app.services.practice_service._answers_open",
        lambda _db, _record: False,
    )
    teacher_view = _to_out(locked, db, teacher)
    student_view = _to_out(locked, db, stu)
    assert teacher_view.score_total == 66
    assert student_view.score_total == 0
    assert student_view.answers_open is False
    assert teacher_view.text_items == []
