# -*- coding: utf-8 -*-
"""学员开户申请：提交 PENDING → 通过生成 STUDENT / 驳回回传理由"""

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import Role, RoleEnum, User, UserMessage
from app.db.models.student_application import StudentAppStatusEnum
from app.schemas.student_application import StudentAppCreate, StudentAppReview
from app.schemas.user import LoginRequest
from app.services.auth_service import AuthService
from app.services.sms_service import clear_sms_log, last_sms
from app.services.student_application_service import StudentApplicationService


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
    from app.core.security import hash_password

    admin_role = Role(code=RoleEnum.ADMIN.value, name="管理员")
    student_role = Role(code=RoleEnum.STUDENT.value, name="学员")
    db.add_all([admin_role, student_role])
    db.flush()
    admin = User(
        username="admin",
        password_hash=hash_password("Admin@123"),
        real_name="管理员",
        role_id=admin_role.id,
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    clear_sms_log()
    return {"admin": admin}


def _apply(db, phone="13800138001"):
    return StudentApplicationService.apply(
        db,
        StudentAppCreate(
            real_name="王同学",
            phone=phone,
            department="眼科",
            reason="住培一年级，申请阅片训练",
        ),
    )


def test_apply_is_pending(db, seeded):
    out = _apply(db)
    assert out.status == StudentAppStatusEnum.PENDING.value
    assert out.created_user_id is None


def test_duplicate_pending_rejected(db, seeded):
    _apply(db)
    with pytest.raises(HTTPException) as exc:
        _apply(db)
    assert exc.value.status_code == 400


def test_approve_creates_student_and_notifies(db, seeded):
    app = _apply(db, "13900139001")
    out = StudentApplicationService.review(
        db,
        reviewer=seeded["admin"],
        application_id=app.id,
        params=StudentAppReview(accept=True, comment="同意"),
    )
    assert out.status == StudentAppStatusEnum.APPROVED.value
    assert out.account_username == "13900139001"
    assert out.temp_password
    assert out.created_user_id

    login = AuthService.login(
        db, LoginRequest(username="13900139001", password=out.temp_password),
    )
    assert login.user_info.role == RoleEnum.STUDENT
    assert login.user_info.must_change_password is True

    sms = last_sms("13900139001")
    assert sms and out.temp_password in sms["content"]

    msgs = db.query(UserMessage).filter(UserMessage.user_id == out.created_user_id).all()
    assert msgs
    assert out.temp_password in msgs[0].content


def test_reject_sends_reason_no_account(db, seeded):
    app = _apply(db, "13700137001")
    out = StudentApplicationService.review(
        db,
        reviewer=seeded["admin"],
        application_id=app.id,
        params=StudentAppReview(accept=False, comment="资料不完整"),
    )
    assert out.status == StudentAppStatusEnum.REJECTED.value
    assert out.created_user_id is None
    assert db.query(User).filter(User.username == "13700137001").first() is None

    sms = last_sms("13700137001")
    assert sms and "资料不完整" in sms["content"]

    status = StudentApplicationService.query_by_phone(db, "13700137001")
    assert status.found is True
    assert status.status == StudentAppStatusEnum.REJECTED.value
    assert status.review_comment == "资料不完整"


def test_reject_requires_comment(db, seeded):
    app = _apply(db, "13600136001")
    with pytest.raises(HTTPException) as exc:
        StudentApplicationService.review(
            db,
            reviewer=seeded["admin"],
            application_id=app.id,
            params=StudentAppReview(accept=False, comment=""),
        )
    assert exc.value.status_code == 400


def test_cannot_review_twice(db, seeded):
    app = _apply(db, "13500135001")
    StudentApplicationService.review(
        db,
        reviewer=seeded["admin"],
        application_id=app.id,
        params=StudentAppReview(accept=True),
    )
    with pytest.raises(HTTPException) as exc:
        StudentApplicationService.review(
            db,
            reviewer=seeded["admin"],
            application_id=app.id,
            params=StudentAppReview(accept=False, comment="再驳"),
        )
    assert exc.value.status_code == 400


def test_existing_student_cannot_reapply(db, seeded):
    from app.core.security import hash_password

    role = db.query(Role).filter(Role.code == RoleEnum.STUDENT.value).one()
    db.add(User(
        username="13800001111",
        password_hash=hash_password("Hy123456"),
        real_name="已有学员",
        phone="13800001111",
        role_id=role.id,
        is_active=True,
    ))
    db.commit()
    with pytest.raises(HTTPException) as exc:
        _apply(db, "13800001111")
    assert exc.value.status_code == 400
