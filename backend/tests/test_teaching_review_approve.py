# -*- coding: utf-8 -*-
"""
教学病例审核通过（2026-08 用户测试报告 A1）

管理员点「通过」必报 500：'str' object has no attribute 'query'。
原因是 generate_case_sn(db, *, prefix=...) 被当成 generate_case_sn("T") 调用，
前缀字符串占了 db 的位置，第一行 db.query(...) 就炸。

审核通过是教学病例入库的唯一入口，这条路断了整个教学库就进不了新病例，
所以这里守两件事：能通过，且生成的编号确实带上了各自的前缀。
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import (
    Role,
    RoleEnum,
    ShareStatusEnum,
    TeachingShare,
    TrainingCase,
    User,
)
from app.schemas.teaching import TeachingReviewParams
from app.services.teaching_service import TeachingService


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
    admin_role = Role(code=RoleEnum.ADMIN.value, name="管理员")
    teacher_role = Role(code=RoleEnum.TEACHER.value, name="带教医师")
    db.add_all([admin_role, teacher_role])
    db.flush()

    admin = User(username="admin", password_hash="x", role_id=admin_role.id)
    teacher = User(username="teacher", password_hash="x", role_id=teacher_role.id)
    db.add_all([admin, teacher])
    db.flush()

    share = TeachingShare(
        share_type="PERMANENT",
        source_type="TRAINING",
        source_case_id=1,
        desensitized_data={
            "title": "重度 NPDR 示教",
            "category": "DR",
            "difficulty": "HARD",
            "gold_dr_grade": "3",
        },
        status=ShareStatusEnum.PENDING.value,
        teacher_id=teacher.id,
    )
    db.add(share)
    db.commit()
    return {"admin": admin, "teacher": teacher, "share": share}


def test_approve_creates_teaching_case(db, seeded):
    """通过审核 → 不抛异常，且真的落了一条教学病例"""
    out = TeachingService.review(
        db,
        reviewer=seeded["admin"],
        share_id=seeded["share"].id,
        params=TeachingReviewParams(accept=True),
    )

    assert out.status == ShareStatusEnum.APPROVED.value

    case = db.query(TrainingCase).one()
    assert seeded["share"].teaching_case_id == case.id
    assert case.title == "重度 NPDR 示教"
    assert case.is_train_case is True


def test_approve_uses_distinct_sn_prefixes(db, seeded):
    """
    case_no 走 T 前缀、case_sn 走 CASE 前缀。
    前缀被当成 db 传进去时这两个字段根本生成不出来，所以顺带守住调用姿势。
    """
    TeachingService.review(
        db,
        reviewer=seeded["admin"],
        share_id=seeded["share"].id,
        params=TeachingReviewParams(accept=True),
    )

    case = db.query(TrainingCase).one()
    assert case.case_no.startswith("T")
    assert case.case_sn.startswith("CASE")
    assert case.case_no != case.case_sn


def test_reject_requires_comment(db, seeded):
    """驳回不填理由应当被挡下（顺带确认驳回路径没被改坏）"""
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as e:
        TeachingService.review(
            db,
            reviewer=seeded["admin"],
            share_id=seeded["share"].id,
            params=TeachingReviewParams(accept=False, comment=""),
        )
    assert e.value.status_code == 400
