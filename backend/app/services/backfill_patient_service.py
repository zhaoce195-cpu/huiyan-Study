# -*- coding: utf-8 -*-
"""
补齐教学病例的模拟患者信息

对应遗留清单 D-001：管理后台的按钮一直存在，但前端调的函数和后端的
路由都没有，点了必定报错，功能从未可用。

只处理**训练病例**的姓名/性别/年龄，以及顺带补齐业务流水号。
筛查病例（biz_screening_case）对应真实受检者，绝不生成也不覆盖 ——
往真实患者记录里塞编造的姓名，是把演示数据混进临床数据。
"""

from typing import Optional

from sqlalchemy.orm import Session

from app.common.mock_patient import mock_patient
from app.db.models import ScreeningCase, TrainingCase
from app.schemas.case_image import BackfillPatientResult
from app.services.case_sn import ensure_case_sn


def backfill_patient_info(
    db: Session,
    *,
    only_empty: bool = True,
    overwrite: bool = False,
) -> BackfillPatientResult:
    result = BackfillPatientResult()

    cases = db.query(TrainingCase).order_by(TrainingCase.id).all()
    result.training_total = len(cases)

    for case in cases:
        name = (case.patient_name or "").strip()
        gender = (case.patient_gender or "U").upper()
        age = case.patient_age or 0

        complete = bool(name) and gender in ("M", "F") and age > 0
        if complete and not overwrite:
            continue
        if not only_empty and not overwrite:
            # 两个开关都为假时不做任何事，而不是「默默按覆盖处理」
            continue

        # 覆盖模式重新生成全部；否则只补空的，已有值原样带入
        gen = mock_patient(
            case.case_no,
            gender=None if overwrite else (gender if gender in ("M", "F") else None),
            age=None if overwrite else (age or None),
        )
        if overwrite or not name:
            case.patient_name = gen["patient_name"]
        if overwrite or gender not in ("M", "F"):
            case.patient_gender = gen["patient_gender"]
        if overwrite or not age:
            case.patient_age = gen["patient_age"]
        result.training_filled += 1

    # 业务流水号：训练与筛查都补，它不是患者信息，缺了会影响检索与对账
    for case in cases:
        if not (case.case_sn or "").strip():
            ensure_case_sn(db, case)
            result.case_sn_filled += 1

    screenings = db.query(ScreeningCase).order_by(ScreeningCase.id).all()
    result.screening_total = len(screenings)
    for case in screenings:
        if not (case.case_sn or "").strip():
            ensure_case_sn(db, case)
            result.case_sn_filled += 1
    # screening_filled 恒为 0：筛查病例对应真实受检者，
    # 不生成也不覆盖其患者信息。字段保留是为了让前端能显式展示
    # 「筛查侧 0 条」，而不是让人以为漏处理了。
    result.screening_filled = 0

    db.commit()
    return result
