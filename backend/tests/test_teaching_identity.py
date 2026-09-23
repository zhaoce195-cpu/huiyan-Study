# -*- coding: utf-8 -*-
"""教学病例对学员只给编号，不给姓名、性别和年龄。"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import Role, RoleEnum, TrainingCase, User
from app.schemas.case_browse import CaseBrowseQuery
from app.services.case_browse_service import CaseBrowseService
from app.services.reading_service import _patient_block


def _db():
    eng = create_engine("sqlite://")
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)()


def _setup(db):
    student_role = Role(code=RoleEnum.STUDENT.value, name="学员")
    teacher_role = Role(code=RoleEnum.TEACHER.value, name="教师")
    db.add_all([student_role, teacher_role])
    db.flush()
    student = User(username="stu", password_hash="x", role_id=student_role.id, is_active=True)
    teacher = User(username="tea", password_hash="x", role_id=teacher_role.id, is_active=True)
    db.add_all([student, teacher])
    db.flush()
    case = TrainingCase(
        case_no="T2026002",
        title="待判读病例",
        description="",
        category="DR",
        difficulty="EASY",
        patient_name="李秀兰",
        patient_gender="F",
        patient_age=58,
        patient_phone="13800001111",
        clinical_info="李秀兰，视力 5.0",
        is_published=True,
        archive_status="ACTIVE",
        creator_id=teacher.id,
    )
    db.add(case)
    db.commit()
    return student, teacher, case


def test_student_list_and_detail_drop_demographics():
    db = _db()
    student, teacher, case = _setup(db)
    listed = CaseBrowseService.list_cases(db, student, CaseBrowseQuery()).list[0]
    assert listed.patient_name == ""
    assert listed.patient_gender == "U"
    assert listed.patient_age == 0
    assert listed.case_no == "T2026002"

    detail = CaseBrowseService.get_detail(db, student, case.id)
    assert detail.patient_name == ""
    assert "李秀兰" not in detail.clinical_info
    assert "视力 5.0" in detail.clinical_info
    assert detail.fundus_only is False

    staff = CaseBrowseService.list_cases(db, teacher, CaseBrowseQuery()).list[0]
    assert staff.patient_name == "李秀兰"
    assert staff.patient_gender == "F"
    assert staff.patient_age == 58
    db.close()


def test_fundus_photo_alone_is_not_missing_materials():
    db = _db()
    student, teacher, _case = _setup(db)
    photo = TrainingCase(
        case_no="T2026011",
        title="只有眼底照",
        description="",
        category="DR",
        difficulty="EASY",
        patient_name="教学编号",
        patient_gender="U",
        clinical_info="眼底彩色照片。请根据图像判断。",
        is_published=True,
        archive_status="ACTIVE",
        creator_id=teacher.id,
    )
    db.add(photo)
    db.commit()
    row = CaseBrowseService.get_detail(db, student, photo.id)
    assert row.fundus_only is True
    assert row.clinical_info == ""
    db.close()


def test_student_cannot_search_by_patient_name():
    db = _db()
    student, teacher, _case = _setup(db)
    assert CaseBrowseService.list_cases(
        db, student, CaseBrowseQuery(keyword="李秀兰")
    ).total == 0
    assert CaseBrowseService.list_cases(
        db, teacher, CaseBrowseQuery(keyword="李秀兰")
    ).total == 1
    assert CaseBrowseService.list_cases(
        db, student, CaseBrowseQuery(keyword="T2026002")
    ).total == 1
    db.close()


def test_reading_source_hides_demographics_from_student():
    db = _db()
    student, teacher, case = _setup(db)
    hidden = _patient_block(case, student)
    assert hidden["patient_name"] == ""
    assert hidden["patient_gender"] == "U"
    assert hidden["patient_age"] == 0
    shown = _patient_block(case, teacher)
    assert shown["patient_name"] == "李秀兰"
    assert shown["patient_age"] == 58
    from app.db.models import TeachingShare
    from app.schemas.teaching import TeachingShareCreate
    from app.services.teaching_service import TeachingService, _student_out
    share = TeachingService.create_temp_share(
        db,
        user=teacher,
        params=TeachingShareCreate(
            source_type="TRAINING", source_case_id=case.id, hide_answers=False,
        ),
    )
    student_view = _student_out(db, db.query(TeachingShare).filter(TeachingShare.id == share.id).one())
    assert student_view.patient_age is None
    assert "李秀兰" not in student_view.clinical_info
    assert "T2026002" in student_view.clinical_info
    assert "视力 5.0" in student_view.clinical_info
    db.close()
