# -*- coding: utf-8 -*-
"""临时分享可以发给某一个年级、轮转批次或带教组，其他学员看不到。"""

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import Role, RoleEnum, TrainingCase, User
from app.schemas.teaching import TeachingShareCreate
from app.services.teaching_service import TeachingService


def _db():
    eng = create_engine("sqlite://")
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)()


def _setup(db):
    teacher_role = Role(code=RoleEnum.TEACHER.value, name="教师")
    student_role = Role(code=RoleEnum.STUDENT.value, name="学员")
    db.add_all([teacher_role, student_role])
    db.flush()
    teacher = User(username="teacher", password_hash="x", real_name="李老师", role_id=teacher_role.id)
    year_a = User(
        username="a", password_hash="x", real_name="甲", role_id=student_role.id,
        study_year="2024级", rotation_batch="2026年上半年", mentor_group="眼底一组",
    )
    year_b = User(
        username="b", password_hash="x", real_name="乙", role_id=student_role.id,
        study_year="2025级", rotation_batch="2026年下半年", mentor_group="眼底二组",
    )
    db.add_all([teacher, year_a, year_b])
    db.flush()
    case = TrainingCase(case_no="T1", title="课堂病例", creator_id=teacher.id)
    db.add(case)
    db.commit()
    return teacher, year_a, year_b, case


def _share(db, teacher, case, scope, value=""):
    return TeachingService.create_temp_share(
        db,
        user=teacher,
        params=TeachingShareCreate(
            source_type="TRAINING",
            source_case_id=case.id,
            share_scope=scope,
            scope_value=value,
        ),
    )


def test_year_share_is_hidden_from_other_grades():
    db = _db()
    teacher, year_a, year_b, case = _setup(db)
    shared = _share(db, teacher, case, "YEAR", "2024级")
    assert shared.share_scope == "YEAR"
    assert shared.scope_value == "2024级"

    seen_a = TeachingService.list_for_student(db, user=year_a)
    seen_b = TeachingService.list_for_student(db, user=year_b)
    assert [item.id for item in seen_a.list] == [shared.id]
    assert seen_b.list == []

    detail = TeachingService.get_student_case_detail(db, share_id=shared.id, user=year_a)
    assert detail.id == shared.id
    with pytest.raises(HTTPException) as err:
        TeachingService.get_student_case_detail(db, share_id=shared.id, user=year_b)
    assert err.value.status_code == 403
    db.close()


def test_batch_and_group_targets_come_from_existing_students():
    db = _db()
    teacher, year_a, year_b, case = _setup(db)
    targets = TeachingService.share_targets(db)
    assert targets.years == ["2024级", "2025级"]
    assert targets.batches == ["2026年上半年", "2026年下半年"]
    assert targets.groups == ["眼底一组", "眼底二组"]
    assert {item.name for item in targets.students} == {"甲", "乙"}

    batch = _share(db, teacher, case, "BATCH", "2026年下半年")
    group = _share(db, teacher, case, "GROUP", "眼底一组")
    everyone = _share(db, teacher, case, "ALL")

    seen_a = {item.id for item in TeachingService.list_for_student(db, user=year_a).list}
    seen_b = {item.id for item in TeachingService.list_for_student(db, user=year_b).list}
    assert seen_a == {group.id, everyone.id}
    assert seen_b == {batch.id, everyone.id}
    db.close()


def test_people_share_reaches_only_selected_students():
    db = _db()
    teacher, year_a, year_b, case = _setup(db)
    shared = TeachingService.create_temp_share(
        db,
        user=teacher,
        params=TeachingShareCreate(
            source_type="TRAINING",
            source_case_id=case.id,
            share_scope="PEOPLE",
            audience_ids=[year_b.id],
        ),
    )
    assert shared.audience_ids == [year_b.id]
    assert shared.audience_label == "乙"
    seen_a = {item.id for item in TeachingService.list_for_student(db, user=year_a).list}
    seen_b = {item.id for item in TeachingService.list_for_student(db, user=year_b).list}
    assert shared.id not in seen_a
    assert shared.id in seen_b
    db.close()


def test_unknown_group_is_rejected():
    db = _db()
    teacher, _year_a, _year_b, case = _setup(db)
    with pytest.raises(HTTPException) as err:
        _share(db, teacher, case, "GROUP", "不存在的组")
    assert err.value.status_code == 400
    db.close()
