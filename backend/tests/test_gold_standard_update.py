# -*- coding: utf-8 -*-
"""
金标准修订 / 发布（教师完善草稿 → 学员可见）

流程：
    AI 建案（未发布草稿）
        → 病例库「完善金标准」
        → 保存草稿：仍未发布，学员不可见
        → 发布并加入实训：is_published + is_train_case
        → 学员抽题 / 阅片能看到
"""

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import (
    CaseArchiveStatusEnum,
    Role,
    RoleEnum,
    TrainingCase,
    User,
)
from app.schemas.case_browse import GoldStandardUpdate
from app.services.case_browse_service import CaseBrowseService
from app.services.practice_service import _ensure_case_visible


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
    student_role = Role(code=RoleEnum.STUDENT.value, name="住培医师")
    db.add_all([admin_role, teacher_role, student_role])
    db.flush()

    admin = User(username="admin", password_hash="x", role_id=admin_role.id)
    teacher = User(username="teacher", password_hash="x", role_id=teacher_role.id)
    other = User(username="other", password_hash="x", role_id=teacher_role.id)
    student = User(username="student", password_hash="x", role_id=student_role.id)
    db.add_all([admin, teacher, other, student])
    db.flush()

    draft = TrainingCase(
        case_no="T2026G01",
        title="AI 建案 · DR 2 级",
        category="DR",
        gold_dr_grade="2",
        gold_diagnosis="（AI 预填，待复核）2 级 中度 NPDR",
        teaching_points="",
        pass_score=60,
        is_published=False,
        is_train_case=False,
        creator_id=teacher.id,
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return {
        "admin": admin,
        "teacher": teacher,
        "other": other,
        "student": student,
        "draft": draft,
    }


def test_save_draft_keeps_unpublished(db, seeded):
    out = CaseBrowseService.update_gold_standard(
        db,
        user=seeded["teacher"],
        case_id=seeded["draft"].id,
        params=GoldStandardUpdate(
            gold_dr_grade="3",
            gold_diagnosis="重度 NPDR，可见静脉串珠",
            teaching_points="注意 4 个象限出血",
            pass_score=70,
            gold_lesions=[{"type": "HE"}],
            publish=False,
        ),
    )

    assert out.is_published is False
    assert out.is_train_case is False
    assert out.gold_dr_grade == "3"
    assert out.gold_diagnosis == "重度 NPDR，可见静脉串珠"
    assert out.teaching_points == "注意 4 个象限出血"
    assert out.pass_score == 70

    case = db.query(TrainingCase).filter(TrainingCase.id == seeded["draft"].id).one()
    assert case.is_published is False
    assert case.is_train_case is False


def test_student_cannot_see_draft(db, seeded):
    with pytest.raises(HTTPException) as exc:
        CaseBrowseService.get_detail(db, user=seeded["student"], case_id=seeded["draft"].id)
    assert exc.value.status_code == 404

    with pytest.raises(HTTPException) as exc:
        _ensure_case_visible(seeded["draft"], seeded["student"])
    assert exc.value.status_code == 403


def test_publish_joins_training_and_student_can_see(db, seeded):
    out = CaseBrowseService.update_gold_standard(
        db,
        user=seeded["teacher"],
        case_id=seeded["draft"].id,
        params=GoldStandardUpdate(
            gold_diagnosis="中度 NPDR",
            teaching_points="后极部微动脉瘤",
            pass_score=65,
            publish=True,
        ),
    )

    assert out.is_published is True
    assert out.is_train_case is True
    assert out.gold_diagnosis == "中度 NPDR"

    student_view = CaseBrowseService.get_detail(
        db, user=seeded["student"], case_id=seeded["draft"].id,
    )
    assert student_view.id == seeded["draft"].id

    case = db.query(TrainingCase).filter(TrainingCase.id == seeded["draft"].id).one()
    _ensure_case_visible(case, seeded["student"])


def test_publish_requires_diagnosis(db, seeded):
    seeded["draft"].gold_diagnosis = ""
    db.commit()

    with pytest.raises(HTTPException) as exc:
        CaseBrowseService.update_gold_standard(
            db,
            user=seeded["teacher"],
            case_id=seeded["draft"].id,
            params=GoldStandardUpdate(gold_diagnosis="  ", publish=True),
        )
    assert exc.value.status_code == 400
    assert "金标准诊断" in str(exc.value.detail)

    case = db.query(TrainingCase).filter(TrainingCase.id == seeded["draft"].id).one()
    assert case.is_published is False
    assert case.is_train_case is False


def test_teacher_cannot_edit_others_case(db, seeded):
    with pytest.raises(HTTPException) as exc:
        CaseBrowseService.update_gold_standard(
            db,
            user=seeded["other"],
            case_id=seeded["draft"].id,
            params=GoldStandardUpdate(gold_diagnosis="篡改", publish=False),
        )
    assert exc.value.status_code == 403


def test_admin_can_edit_others_case(db, seeded):
    out = CaseBrowseService.update_gold_standard(
        db,
        user=seeded["admin"],
        case_id=seeded["draft"].id,
        params=GoldStandardUpdate(gold_diagnosis="管理员复核", publish=True),
    )
    assert out.is_published is True
    assert out.gold_diagnosis == "管理员复核"


def test_student_cannot_update(db, seeded):
    with pytest.raises(HTTPException) as exc:
        CaseBrowseService.update_gold_standard(
            db,
            user=seeded["student"],
            case_id=seeded["draft"].id,
            params=GoldStandardUpdate(gold_diagnosis="学员乱写", publish=True),
        )
    assert exc.value.status_code == 403


def test_archived_cannot_update(db, seeded):
    seeded["draft"].archive_status = CaseArchiveStatusEnum.ARCHIVED.value
    db.commit()

    with pytest.raises(HTTPException) as exc:
        CaseBrowseService.update_gold_standard(
            db,
            user=seeded["teacher"],
            case_id=seeded["draft"].id,
            params=GoldStandardUpdate(gold_diagnosis="归档后改", publish=False),
        )
    assert exc.value.status_code == 400


def test_invalid_grade_rejected(db, seeded):
    with pytest.raises(HTTPException) as exc:
        CaseBrowseService.update_gold_standard(
            db,
            user=seeded["teacher"],
            case_id=seeded["draft"].id,
            params=GoldStandardUpdate(gold_dr_grade="9", publish=False),
        )
    assert exc.value.status_code == 400


def test_save_draft_on_published_does_not_unpublish(db, seeded):
    seeded["draft"].is_published = True
    seeded["draft"].is_train_case = True
    db.commit()

    out = CaseBrowseService.update_gold_standard(
        db,
        user=seeded["teacher"],
        case_id=seeded["draft"].id,
        params=GoldStandardUpdate(
            teaching_points="补一句教学要点",
            publish=False,
        ),
    )
    assert out.is_published is True
    assert out.is_train_case is True
    assert out.teaching_points == "补一句教学要点"
