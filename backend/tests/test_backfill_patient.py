# -*- coding: utf-8 -*-
"""
教学病例模拟患者信息补齐

对应遗留清单 D-001。

这里守的核心是一条边界：训练病例可以生成模拟信息，
筛查病例对应真实受检者，一律不碰。
往真实患者记录里塞编造的姓名，是把演示数据混进临床数据。
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.common.mock_patient import mock_patient
from app.db.base import Base
from app.db.models import Role, RoleEnum, ScreeningCase, TrainingCase, User
from app.services.backfill_patient_service import backfill_patient_info


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture()
def seeded(db):
    role = Role(code=RoleEnum.ADMIN.value, name="管理员")
    db.add(role)
    db.flush()
    admin = User(username="admin", password_hash="x", role_id=role.id)
    db.add(admin)
    db.flush()

    db.add(TrainingCase(case_no="T-EMPTY", title="全空", category="DR",
                        creator_id=admin.id))
    db.add(TrainingCase(case_no="T-PARTIAL", title="有年龄", category="DR",
                        patient_age=52, patient_gender="M", creator_id=admin.id))
    db.add(TrainingCase(case_no="T-FULL", title="齐全", category="DR",
                        patient_name="王伟", patient_age=61, patient_gender="M",
                        creator_id=admin.id))
    # 筛查表的字段名与训练表不同：gender / age（无 patient_ 前缀）
    db.add(ScreeningCase(case_no="S-001", patient_name="真实受检者",
                         age=44, gender="F", submit_user_id=admin.id))
    db.commit()
    return admin


def _case(db, no):
    return db.query(TrainingCase).filter(TrainingCase.case_no == no).first()


# --------------------------------------------------------------------------
# 生成本身
# --------------------------------------------------------------------------

def test_generation_is_deterministic():
    """
    同一病例号永远得到同一组值。否则重跑一次数据就变一遍，
    已进 PACS 的 DICOM（PatientName 取自本字段）也会与业务库对不上。
    """
    assert mock_patient("T-001") == mock_patient("T-001")


def test_different_cases_get_different_names():
    names = {mock_patient(f"T-{i:03d}")["patient_name"] for i in range(40)}
    assert len(names) > 10, "生成过于集中，几十个病例只有几个名字"


def test_existing_values_are_kept():
    """已有性别/年龄要沿用，不能被生成值顶掉"""
    got = mock_patient("T-001", gender="F", age=66)
    assert got["patient_gender"] == "F"
    assert got["patient_age"] == 66


def test_generated_age_is_plausible():
    for i in range(50):
        age = mock_patient(f"T-{i}")["patient_age"]
        assert 35 <= age <= 79, f"生成了不合理的年龄 {age}"


# --------------------------------------------------------------------------
# 补齐行为
# --------------------------------------------------------------------------

def test_empty_case_is_filled(db, seeded):
    backfill_patient_info(db, only_empty=True)
    c = _case(db, "T-EMPTY")
    assert c.patient_name and c.patient_gender in ("M", "F") and c.patient_age > 0


def test_partial_case_keeps_existing_values(db, seeded):
    """只补空的：已有的年龄性别不能被改掉"""
    backfill_patient_info(db, only_empty=True)
    c = _case(db, "T-PARTIAL")
    assert c.patient_age == 52
    assert c.patient_gender == "M"
    assert c.patient_name


def test_complete_case_untouched_without_overwrite(db, seeded):
    backfill_patient_info(db, only_empty=True)
    assert _case(db, "T-FULL").patient_name == "王伟"


def test_overwrite_regenerates(db, seeded):
    backfill_patient_info(db, only_empty=False, overwrite=True)
    assert _case(db, "T-FULL").patient_name != "王伟"


def test_screening_case_is_never_touched(db, seeded):
    """
    筛查病例对应真实受检者。哪怕开了强制覆盖也不能碰 ——
    往真实患者记录里塞编造的姓名，是把演示数据混进临床数据。
    """
    backfill_patient_info(db, only_empty=False, overwrite=True)
    sc = db.query(ScreeningCase).first()
    assert sc.patient_name == "真实受检者"
    assert sc.age == 44
    assert sc.gender == "F"


def test_result_reports_screening_as_zero(db, seeded):
    """
    筛查侧显式报 0，而不是不报 —— 不报会让人以为漏处理了。
    """
    r = backfill_patient_info(db, only_empty=True)
    assert r.screening_total == 1
    assert r.screening_filled == 0
    assert r.training_total == 3


def test_both_switches_off_does_nothing(db, seeded):
    """
    两个开关都为假时什么都不做，而不是默默按覆盖处理。
    """
    r = backfill_patient_info(db, only_empty=False, overwrite=False)
    assert r.training_filled == 0
    assert _case(db, "T-EMPTY").patient_name in ("", None)


def test_rerun_is_stable(db, seeded):
    """重复执行结果一致，不会让数据来回变"""
    backfill_patient_info(db, only_empty=True)
    first = _case(db, "T-EMPTY").patient_name
    backfill_patient_info(db, only_empty=True)
    assert _case(db, "T-EMPTY").patient_name == first
