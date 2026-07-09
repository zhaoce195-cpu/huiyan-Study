"""
全局唯一病例编号 case_sn 生成器
格式：CASE + YYYYMMDD + 6位随机十进制
跨 ScreeningCase + TrainingCase 全局唯一，碰撞重试 3 次
"""

import random
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session


def _exists(db: Session, sn: str) -> bool:
    """同时查两张主表，确保跨表唯一。"""
    from app.db.models import ScreeningCase, TrainingCase
    if db.query(ScreeningCase.id).filter(ScreeningCase.case_sn == sn).first():
        return True
    if db.query(TrainingCase.id).filter(TrainingCase.case_sn == sn).first():
        return True
    return False


def generate_case_sn(db: Session, *, prefix: str = "CASE", retries: int = 5) -> str:
    """生成形如 CASE20260526123456 的全局唯一编号。"""
    today = datetime.now().strftime("%Y%m%d")
    for _ in range(retries):
        rand = random.randint(100000, 999999)
        sn = f"{prefix}{today}{rand}"
        if not _exists(db, sn):
            return sn
    # 极端碰撞兜底：附加时间戳毫秒
    ms = datetime.now().strftime("%H%M%S%f")[:9]
    return f"{prefix}{today}{ms}"


def ensure_case_sn(db: Session, case, *, commit: bool = False) -> str:
    """如果 case.case_sn 为空则生成并写入；返回 case_sn。"""
    if case.case_sn:
        return case.case_sn
    case.case_sn = generate_case_sn(db)
    if commit:
        db.commit()
    return case.case_sn


__all__ = ["generate_case_sn", "ensure_case_sn"]
