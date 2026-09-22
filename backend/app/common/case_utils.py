"""
病例通用工具（去重重复实现）
- flatten_image_paths: 把 image_paths JSON ({OD/OS/OU: [...]}) 拍平成图片列表
- mask_phone_by_role:  按角色对 phone 做脱敏（ADMIN 完整 / TEACHER 脱敏 / 其他隐藏）
"""
from typing import List, Optional, Tuple

from app.db.models.user import RoleEnum
from app.services.patient_mock import mask_phone


def unique_image_urls(urls: List[str]) -> List[str]:
    """同一地址只保留第一次出现。一张图挂在左右眼两栏时，不能当成两张影像。"""
    seen = set()
    out: List[str] = []
    for url in urls:
        if not isinstance(url, str) or not url or url in seen:
            continue
        seen.add(url)
        out.append(url)
    return out


def flatten_image_paths(image_paths: Optional[dict]) -> List[str]:
    """把 image_paths JSON 拍平成有序 URL 列表（OD → OS → OU → UK），相同地址只留一张。"""
    if not isinstance(image_paths, dict):
        return []
    out: List[str] = []
    for side in ("OD", "OS", "OU", "UK"):
        arr = image_paths.get(side) or []
        if isinstance(arr, list):
            out.extend([p for p in arr if isinstance(p, str)])
    return unique_image_urls(out)


def collapse_duplicate_image_paths(image_paths: Optional[dict]) -> dict:
    """同一张图出现在多个眼别时只留第一次。左右眼各有自己的文件时原样保留。"""
    if not isinstance(image_paths, dict):
        return {}
    seen = set()
    out: dict = {}
    for side in ("OD", "OS", "OU", "UK"):
        arr = image_paths.get(side) or []
        if not isinstance(arr, list):
            continue
        kept = []
        for url in arr:
            if not isinstance(url, str) or not url or url in seen:
                continue
            seen.add(url)
            kept.append(url)
        if kept:
            out[side] = kept
    return out


def mask_phone_by_role(phone: str, role_code: Optional[str]) -> Tuple[str, bool]:
    """
    按角色返回 (展示用手机号, 是否完整可见)
    - ADMIN     → 完整明文 / True
    - TEACHER   → 脱敏（138****5678） / False
    - 其他角色  → 空串 / False
    """
    raw = (phone or "").strip()
    if role_code == RoleEnum.ADMIN.value:
        return raw, True
    if role_code == RoleEnum.TEACHER.value:
        return mask_phone(raw), False
    return "", False
