# -*- coding: utf-8 -*-
"""
教学病例的模拟患者信息

训练病例来自公开数据集（IDRiD 等），本就没有患者身份。教学场景里
需要一个称呼与基本人口学信息，界面上也一直标注为「模拟患者信息」。

与本项目此前拒绝伪造的那些字段划清界限：
    检查日期、眼别、像素间距、SNOMED 编码 —— 一律不造。
    它们是**临床事实**，编一个会直接导致判读错误。
    姓名/性别/年龄在教学病例里是**展示标签**，不参与任何判读，
    且明确标注为模拟。

生成是确定性的：同一个病例号永远得到同一组值。
    · 重复执行不会让数据来回变；
    · 已经转换进 PACS 的 DICOM（PatientName 取自本字段）
      不会因为再跑一次补齐而与业务库对不上。
"""

import hashlib
from typing import Dict, Optional

# 常见姓氏与名，仅用于生成可读的称呼
_SURNAMES = (
    "李", "王", "张", "刘", "陈", "杨", "赵", "黄", "周", "吴",
    "徐", "孙", "胡", "朱", "高", "林", "何", "郭", "马", "罗",
)
_GIVEN_M = ("建国", "志强", "伟", "军", "磊", "涛", "明", "勇", "杰", "峰")
_GIVEN_F = ("秀英", "娜", "敏", "静", "丽", "芳", "燕", "洁", "霞", "梅")


def _digest(case_no: str) -> bytes:
    return hashlib.sha256((case_no or "").encode("utf-8")).digest()


def mock_patient(case_no: str, gender: Optional[str] = None,
                 age: Optional[int] = None) -> Dict[str, object]:
    """
    由病例号派生一组模拟患者信息。

    :param gender: 已有性别则沿用，不覆盖
    :param age: 已有年龄则沿用，不覆盖
    """
    d = _digest(case_no)

    sex = (gender or "").upper()
    if sex not in ("M", "F"):
        sex = "M" if d[0] % 2 == 0 else "F"

    surname = _SURNAMES[d[1] % len(_SURNAMES)]
    pool = _GIVEN_M if sex == "M" else _GIVEN_F
    name = surname + pool[d[2] % len(pool)]

    if not age or age <= 0:
        # 眼底病变筛查人群以中老年为主，取 35～79 岁
        age = 35 + (d[3] % 45)

    return {"patient_name": name, "patient_gender": sex, "patient_age": int(age)}
