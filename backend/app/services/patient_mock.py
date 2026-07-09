"""
模拟患者信息生成器
==================
为批量导入的眼底病例自动生成虚拟但真实的患者信息：
- 姓名（中文真实姓名 + 男女区分）
- 性别（M/F）
- 年龄（35~85，符合糖尿病眼底病高发区间）
- 手机号（中国大陆 11 位合法格式：13/14/15/16/17/18/19 段）

唯一性：手机号在 ScreeningCase / TrainingCase 两表内做去重检测，
碰撞重试 5 次，仍冲突则强制 fallback 到时间戳后缀。

应用场景：
- IDRiD 批量导入（idrid_import_service）
- 医生 / 管理员上传眼底图（screening_service.upload_single）
- 旧病例补齐（backfill_patient_info）
"""

from __future__ import annotations

import random
from typing import Tuple

from sqlalchemy.orm import Session

from app.db.models import GenderEnum


# ============================================================
#                     中文姓名词库
# ============================================================
# 常见百家姓（覆盖大陆人口约 90%）
_SURNAMES = [
    "李", "王", "张", "刘", "陈", "杨", "黄", "赵", "吴", "周",
    "徐", "孙", "胡", "朱", "高", "林", "何", "郭", "马", "罗",
    "梁", "宋", "郑", "谢", "韩", "唐", "冯", "于", "董", "萧",
    "程", "曹", "袁", "邓", "许", "傅", "沈", "曾", "彭", "吕",
    "苏", "卢", "蒋", "蔡", "贾", "丁", "魏", "薛", "叶", "阎",
    "余", "潘", "杜", "戴", "夏", "钟", "汪", "田", "任", "姜",
    "范", "方", "石", "姚", "谭", "廖", "邹", "熊", "金", "陆",
]

_MALE_GIVEN = [
    # 双字名
    "建国", "建华", "国强", "志强", "伟", "勇", "军", "杰", "涛", "鑫",
    "磊", "斌", "波", "辉", "凯", "亮", "刚", "鹏", "超", "锋",
    "永康", "立军", "伟东", "建军", "永生", "广平", "卫国", "卫东",
    "玉成", "宝山", "宝国", "宝忠", "玉良", "玉龙", "金宝", "金山",
    "树林", "树森", "明德", "明哲", "明辉", "正阳", "正华", "晓东",
    "兆丰", "兆辉", "宏伟", "宏志", "义贵", "义林", "学斌",
]

_FEMALE_GIVEN = [
    "秀英", "桂英", "桂兰", "玉兰", "玉珍", "兰英", "凤英", "凤兰",
    "美玲", "美兰", "美英", "丽华", "丽萍", "丽娟", "丽芳", "翠兰",
    "淑芬", "淑珍", "淑兰", "淑梅", "秀梅", "秀芳", "秀珍", "秀华",
    "桂珍", "桂芳", "桂芬", "桂芝", "玉梅", "玉芳", "玉芬", "玉霞",
    "晓燕", "晓梅", "晓敏", "晓红", "晓琳", "雪梅", "雪芳", "雪琴",
    "春兰", "春梅", "春霞", "春艳", "建华", "金兰", "金凤", "金花",
    "海燕", "红梅", "莉莉", "敏", "燕", "霞", "梅", "芳", "莉",
]


# ============================================================
#                     手机号 / 年龄
# ============================================================

_MOBILE_PREFIXES = [
    "130", "131", "132", "133", "134", "135", "136", "137", "138", "139",
    "150", "151", "152", "153", "155", "156", "157", "158", "159",
    "170", "171", "176", "177", "178",
    "180", "181", "182", "183", "184", "185", "186", "187", "188", "189",
    "190", "191", "192", "193", "195", "196", "197", "198", "199",
]


def random_chinese_name(gender: str) -> str:
    """
    随机中文姓名，姓 + 名 1~2 字。
    gender: 'M' / 'F'
    """
    surname = random.choice(_SURNAMES)
    pool = _MALE_GIVEN if gender == GenderEnum.MALE.value else _FEMALE_GIVEN
    given = random.choice(pool)
    return f"{surname}{given}"


def random_gender() -> str:
    """随机性别 M / F（不返回 U，因为模拟数据要明确性别）"""
    return random.choice([GenderEnum.MALE.value, GenderEnum.FEMALE.value])


def random_age(low: int = 35, high: int = 85) -> int:
    """
    随机年龄。糖尿病眼底病高发区间默认 35~85。
    """
    return random.randint(low, high)


def random_mobile() -> str:
    """生成合法的中国大陆 11 位手机号。"""
    prefix = random.choice(_MOBILE_PREFIXES)
    suffix = "".join(str(random.randint(0, 9)) for _ in range(8))
    return f"{prefix}{suffix}"


def _phone_exists(db: Session, phone: str) -> bool:
    """跨 ScreeningCase + TrainingCase 检查手机号唯一性。"""
    from app.db.models import ScreeningCase, TrainingCase
    if db.query(ScreeningCase.id).filter(ScreeningCase.patient_phone == phone).first():
        return True
    if db.query(TrainingCase.id).filter(TrainingCase.patient_phone == phone).first():
        return True
    return False


def generate_unique_mobile(db: Session, *, retries: int = 5) -> str:
    """生成数据库内不冲突的手机号；碰撞重试 5 次。"""
    for _ in range(retries):
        ph = random_mobile()
        if not _phone_exists(db, ph):
            return ph
    # 极端碰撞兜底：换一个号段并附时间戳尾段
    import time
    fallback = f"199{int(time.time() % 100000000):08d}"
    return fallback


# ============================================================
#                     聚合：一次性返回完整患者信息
# ============================================================

class MockPatient:
    """便于一次拿回所有字段；调用方按需赋值。"""
    __slots__ = ("name", "gender", "age", "phone")

    def __init__(self, name: str, gender: str, age: int, phone: str):
        self.name = name
        self.gender = gender
        self.age = age
        self.phone = phone

    def as_dict(self) -> dict:
        return {
            "patient_name": self.name,
            "gender": self.gender,
            "age": self.age,
            "patient_phone": self.phone,
        }


def generate_mock_patient(
    db: Session,
    *,
    age_low: int = 35,
    age_high: int = 85,
    fixed_gender: str = "",
) -> MockPatient:
    """
    一次性生成完整模拟患者信息。
    fixed_gender: 'M'/'F' 显式指定（不传 = 随机）。
    """
    gender = fixed_gender if fixed_gender in ("M", "F") else random_gender()
    name = random_chinese_name(gender)
    age = random_age(age_low, age_high)
    phone = generate_unique_mobile(db)
    return MockPatient(name=name, gender=gender, age=age, phone=phone)


# ============================================================
#                     工具：脱敏手机号
# ============================================================

def mask_phone(phone: str) -> str:
    """`13812345678` → `138****5678`，便于教师 / 学员视图脱敏展示。"""
    if not phone or len(phone) != 11 or not phone.isdigit():
        return phone or ""
    return f"{phone[:3]}****{phone[7:]}"


__all__ = [
    "MockPatient",
    "generate_mock_patient",
    "random_chinese_name",
    "random_gender",
    "random_age",
    "random_mobile",
    "generate_unique_mobile",
    "mask_phone",
]
