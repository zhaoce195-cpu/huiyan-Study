# -*- coding: utf-8 -*-
"""
教师 AI 批量筛查：确认报告 / 转诊

入口在前端侧栏，本文件守后端硬约束：
    未绑定手机号不能确认；确认后 report_status=confirmed；
    转诊写入备注。
"""

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import (
    Role,
    RoleEnum,
    ScreeningCase,
    ScreeningResult,
    ScreeningStatusEnum,
    User,
)
from app.schemas.screening import ConfirmReportParams, ReferParams
from app.services.screening_service import ScreeningService


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
    teacher_role = Role(code=RoleEnum.TEACHER.value, name="带教医师")
    patient_role = Role(code=RoleEnum.PATIENT.value, name="体检者")
    db.add_all([teacher_role, patient_role])
    db.flush()
    teacher = User(username="teacher", password_hash="x", role_id=teacher_role.id)
    patient = User(
        username="p13800001111",
        password_hash="x",
        role_id=patient_role.id,
        phone="13800001111",
    )
    db.add_all([teacher, patient])
    db.flush()

    case = ScreeningCase(
        case_no="T2026S01",
        patient_name="王建国",
        gender="M",
        age=64,
        patient_phone="",
        status=ScreeningStatusEnum.COMPLETED.value,
        report_status="pending",
        submit_user_id=teacher.id,
        image_paths={"OD": ["/static/screening/demo.jpg"]},
        image_count=1,
    )
    db.add(case)
    db.flush()
    db.add(ScreeningResult(
        case_id=case.id,
        eye_side="OD",
        dr_grade="4",
        risk_level="HIGH",
        risk_score=0.97,
        referral_required=1,
    ))
    db.commit()
    db.refresh(case)
    return {"teacher": teacher, "patient": patient, "case": case}


def test_confirm_requires_patient_phone(db, seeded):
    with pytest.raises(HTTPException) as exc:
        ScreeningService.confirm_report(
            db,
            ConfirmReportParams(task_id="T2026S01"),
            seeded["teacher"],
        )
    assert exc.value.status_code == 400
    assert "手机号" in str(exc.value.detail)


def test_confirm_binds_patient_and_marks_confirmed(db, seeded):
    case = seeded["case"]
    case.patient_phone = "13800001111"
    db.commit()

    out = ScreeningService.confirm_report(
        db,
        ConfirmReportParams(task_id="T2026S01", diagnosis="增殖性 DR，建议转诊"),
        seeded["teacher"],
    )
    db.refresh(case)
    assert case.report_status == "confirmed"
    assert case.status == ScreeningStatusEnum.REVIEWED.value
    assert case.patient_user_id == seeded["patient"].id
    assert out.patient_bound is True
    assert out.patient_phone == "13800001111"


def test_refer_appends_remark(db, seeded):
    ScreeningService.refer(
        db,
        ReferParams(task_id="T2026S01", target_hospital="同仁医院眼科", note="高危"),
        seeded["teacher"],
    )
    case = db.query(ScreeningCase).filter(ScreeningCase.case_no == "T2026S01").one()
    assert "同仁医院眼科" in case.remark
    assert "高危" in case.remark
