# -*- coding: utf-8 -*-
"""
科室按医院隔离（2026-08 用户测试报告 B2）

「在 ID 为 2 的医院创建科室，切换到其他医院视角，发现该科室也被创建了，
  所有医院显示的科室列表完全一致。」

原来 biz_department 根本没有医院字段，list_departments 收下 hospital_id
后原样丢回出参、从不参与查询，所以谈不上任何隔离。

现在的语义：
  - hospital_id 有值 → 只在这家医院下可见
  - hospital_id 为 NULL → 全院通用，任何医院都看得到（存量科室都是这种）
  - 编码在同一医院内唯一，不同医院可以重名
"""

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
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


def test_department_is_not_visible_to_other_hospitals(db):
    """报告里的原始场景：在 B 医院建的科室不该出现在 A 医院下"""
    CommonService.create_department(
        db, DepartmentSaveParams(hospitalId=HOSPITAL_B, code="OPHTH", name="B院眼科")
    )

    assert _names(CommonService.list_departments(db, hospital_id=HOSPITAL_B)) == {"B院眼科"}
    assert _names(CommonService.list_departments(db, hospital_id=HOSPITAL_A)) == set()


def test_global_department_visible_everywhere(db):
    """不填医院 = 全院通用；存量科室都是这种，行为要保持不变"""
    CommonService.create_department(
        db, DepartmentSaveParams(code="INFO", name="信息中心")
    )
    CommonService.create_department(
        db, DepartmentSaveParams(hospitalId=HOSPITAL_A, code="OPHTH", name="A院眼科")
    )

    assert _names(CommonService.list_departments(db, hospital_id=HOSPITAL_A)) == {
        "信息中心",
        "A院眼科",
    }
    assert _names(CommonService.list_departments(db, hospital_id=HOSPITAL_B)) == {"信息中心"}
    # 不指定医院 = 后台总览，看得到全部
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


def test_duplicate_code_among_global_departments_rejected(db):
    """
    数据库的 UNIQUE(hospital_id, code) 对多个 NULL 是放行的，
    所以全院通用科室之间的重复必须由 service 层挡下来。
    """
    CommonService.create_department(db, DepartmentSaveParams(code="INFO", name="信息中心"))
    with pytest.raises(HTTPException) as e:
        CommonService.create_department(db, DepartmentSaveParams(code="INFO", name="信息科"))
    assert e.value.status_code == 409


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
