# -*- coding: utf-8 -*-
"""
科室按医院隔离（2026-08 用户测试报告 B2）

「在 ID 为 2 的医院创建科室，切换到其他医院视角，发现该科室也被创建了，
  所有医院显示的科室列表完全一致。」

原来 biz_department 根本没有医院字段，list_departments 收下 hospital_id
后原样丢回出参、从不参与查询，所以谈不上任何隔离。

现在的语义：
  - 新建和修改都必须指定医院
  - 按医院查询时只返回这家医院的科室，未归属的旧数据不混进来
  - 不指定医院的总览仍能看到全部
  - 编码在同一医院内唯一，不同医院可以重名
"""

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import Department
from app.schemas.common import DepartmentSaveParams
from app.services.common_service import CommonService

HOSPITAL_A = 1
HOSPITAL_B = 2


@pytest.fixture()
def db():
    eng = create_engine("sqlite://")
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    try:
        yield s
    finally:
        s.close()


def _names(items) -> set:
    return {i.name for i in items}


def test_same_name_departments_do_not_share_people(db):
    """两家医院都可以有「眼科」，人员挂在各自的科室记录上，不能串。"""
    from app.db.models import Role, RoleEnum, User

    role = Role(code=RoleEnum.TEACHER.value, name="带教老师")
    db.add(role)
    db.commit()
    eye_a = CommonService.create_department(
        db, DepartmentSaveParams(hospitalId=HOSPITAL_A, code="OPHTH", name="眼科")
    )
    eye_b = CommonService.create_department(
        db, DepartmentSaveParams(hospitalId=HOSPITAL_B, code="OPHTH", name="眼科")
    )
    db.add(User(
        username="a1", password_hash="x", real_name="周启明", title="主治医师",
        department="眼科", department_id=int(eye_a.id), role_id=role.id,
    ))
    db.add(User(
        username="b1", password_hash="x", real_name="沈予安", title="主任医师",
        department="眼科", department_id=int(eye_b.id), role_id=role.id,
    ))
    db.commit()

    a_rows = CommonService.list_departments(db, hospital_id=HOSPITAL_A)
    b_rows = CommonService.list_departments(db, hospital_id=HOSPITAL_B)
    assert [m.real_name for m in a_rows[0].members] == ["周启明"]
    assert [m.real_name for m in b_rows[0].members] == ["沈予安"]


def test_department_is_not_visible_to_other_hospitals(db):
    """报告里的原始场景：在 B 医院建的科室不该出现在 A 医院下"""
    CommonService.create_department(
        db, DepartmentSaveParams(hospitalId=HOSPITAL_B, code="OPHTH", name="B院眼科")
    )

    assert _names(CommonService.list_departments(db, hospital_id=HOSPITAL_B)) == {"B院眼科"}
    assert _names(CommonService.list_departments(db, hospital_id=HOSPITAL_A)) == set()


def test_new_department_requires_a_hospital(db):
    """不选医院就不能建，避免又变成每家医院都能看到的公共科室"""
    with pytest.raises(HTTPException) as e:
        CommonService.create_department(db, DepartmentSaveParams(code="INFO", name="信息中心"))
    assert e.value.status_code == 400


def test_legacy_unassigned_department_is_not_listed_under_every_hospital(db):
    """旧数据没有医院。总览还能看到，但任何一家医院的列表里都不该出现。"""
    db.add(Department(code="INFO", name="信息中心", hospital_id=None))
    db.commit()
    CommonService.create_department(
        db, DepartmentSaveParams(hospitalId=HOSPITAL_A, code="OPHTH", name="A院眼科")
    )

    assert _names(CommonService.list_departments(db, hospital_id=HOSPITAL_A)) == {"A院眼科"}
    assert _names(CommonService.list_departments(db, hospital_id=HOSPITAL_B)) == set()
    assert _names(CommonService.list_departments(db)) == {"信息中心", "A院眼科"}


def test_same_code_allowed_across_hospitals(db):
    """两家医院都该能有自己的「眼科 / OPHTH」"""
    CommonService.create_department(
        db, DepartmentSaveParams(hospitalId=HOSPITAL_A, code="OPHTH", name="A院眼科")
    )
    CommonService.create_department(
        db, DepartmentSaveParams(hospitalId=HOSPITAL_B, code="OPHTH", name="B院眼科")
    )

    assert _names(CommonService.list_departments(db, hospital_id=HOSPITAL_A)) == {"A院眼科"}
    assert _names(CommonService.list_departments(db, hospital_id=HOSPITAL_B)) == {"B院眼科"}


def test_duplicate_code_within_same_hospital_rejected(db):
    CommonService.create_department(
        db, DepartmentSaveParams(hospitalId=HOSPITAL_A, code="OPHTH", name="眼科")
    )
    with pytest.raises(HTTPException) as e:
        CommonService.create_department(
            db, DepartmentSaveParams(hospitalId=HOSPITAL_A, code="OPHTH", name="眼科二部")
        )
    assert e.value.status_code == 409


def test_clearing_hospital_on_update_rejected(db):
    out = CommonService.create_department(
        db, DepartmentSaveParams(hospitalId=HOSPITAL_A, code="OPHTH", name="眼科")
    )
    with pytest.raises(HTTPException) as e:
        CommonService.update_department(
            db, int(out.id), DepartmentSaveParams(code="OPHTH", name="眼科")
        )
    assert e.value.status_code == 400


def test_unknown_hospital_rejected(db):
    with pytest.raises(HTTPException) as e:
        CommonService.create_department(
            db, DepartmentSaveParams(hospitalId=9999, code="X", name="不存在的医院")
        )
    assert e.value.status_code == 400


def test_moving_department_between_hospitals(db):
    """改所属医院后，可见范围要跟着走"""
    out = CommonService.create_department(
        db, DepartmentSaveParams(hospitalId=HOSPITAL_A, code="OPHTH", name="眼科")
    )
    CommonService.update_department(
        db, int(out.id), DepartmentSaveParams(hospitalId=HOSPITAL_B, code="OPHTH", name="眼科")
    )

    assert _names(CommonService.list_departments(db, hospital_id=HOSPITAL_A)) == set()
    assert _names(CommonService.list_departments(db, hospital_id=HOSPITAL_B)) == {"眼科"}


def test_moving_into_a_hospital_that_already_has_the_code(db):
    CommonService.create_department(
        db, DepartmentSaveParams(hospitalId=HOSPITAL_B, code="OPHTH", name="B院眼科")
    )
    out = CommonService.create_department(
        db, DepartmentSaveParams(hospitalId=HOSPITAL_A, code="OPHTH", name="A院眼科")
    )
    with pytest.raises(HTTPException) as e:
        CommonService.update_department(
            db,
            int(out.id),
            DepartmentSaveParams(hospitalId=HOSPITAL_B, code="OPHTH", name="A院眼科"),
        )
    assert e.value.status_code == 409
