# -*- coding: utf-8 -*-
"""课堂分享可以先藏金标准，老师公布后学员才看得到。"""

from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import Role, RoleEnum, TeachingShare, TrainingCase, User
from app.schemas.teaching import TeachingShareCreate
from app.services.teaching_service import TeachingService, _student_out


def _db():
    eng = create_engine("sqlite://")
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)()


def _people(db):
    role = Role(code=RoleEnum.TEACHER.value, name="教师")
    db.add(role)
    db.flush()
    teacher = User(username="teacher", password_hash="x", real_name="李老师", role_id=role.id)
    db.add(teacher)
    db.flush()
    case = TrainingCase(
        case_no="T2026002",
        title="轻度 NPDR · DR 1 级",
        description="标准诊断写在描述里",
        category="DR",
        difficulty="EASY",
        patient_name="隐藏",
        patient_gender="F",
        patient_phone="13800000000",
        clinical_info="糖尿病史",
        teaching_points="只有微动脉瘤。",
        gold_dr_grade="1",
        gold_diagnosis="轻度 NPDR",
        gold_lesions=[{"type": "MA", "count": 2}],
        gold_annotations=[{"tool": "rect", "label": "MA", "points": [{"x": 1, "y": 1}, {"x": 2, "y": 2}]}],
        creator_id=teacher.id,
    )
    db.add(case)
    db.commit()
    return teacher, case


def test_hidden_share_strips_gold_until_teacher_reveals():
    db = _db()
    teacher, case = _people(db)
    hidden = TeachingService.create_temp_share(
        db,
        user=teacher,
        params=TeachingShareCreate(source_type="TRAINING", source_case_id=case.id, hide_answers=True),
    )
    assert hidden.answers_revealed is False
    assert "轻度 NPDR" in hidden.desensitized_data["gold_diagnosis"]

    student = _student_out(db, db.query(TeachingShare).filter(TeachingShare.id == hidden.id).one())
    assert student.answers_revealed is False
    assert student.gold_diagnosis == ""
    assert student.gold_grade_text == ""
    assert student.teaching_points == ""
    assert student.lesions == []
    assert student.annotations == []
    assert student.title == "课堂病例 T2026002"
    assert "DR 1" not in student.title
    assert student.description == ""
    assert student.clinical_info == ""

    shown = TeachingService.reveal_answers(db, user=teacher, share_id=hidden.id)
    assert shown.answers_revealed is True
    again = _student_out(db, db.query(TeachingShare).filter(TeachingShare.id == hidden.id).one())
    assert again.gold_diagnosis == "轻度 NPDR"
    assert again.teaching_points == "只有微动脉瘤。"
    assert again.lesions[0]["name"] == "微动脉瘤"
    assert again.clinical_info == ""
    db.close()


def test_archive_share_still_shows_answers():
    db = _db()
    teacher, case = _people(db)
    share = TeachingShare(
        share_type="PERMANENT",
        source_type="TRAINING",
        source_case_id=case.id,
        desensitized_data={"title": case.title, "gold_diagnosis": "轻度 NPDR"},
        status="APPROVED",
        answers_revealed=False,
        teacher_id=teacher.id,
        expired_at=datetime.now() + timedelta(hours=1),
    )
    db.add(share)
    db.commit()
    student = _student_out(db, share)
    assert student.answers_revealed is True
    assert student.gold_diagnosis == "轻度 NPDR"
    db.close()
