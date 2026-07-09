"""
病例通用工具（去重重复实现）
- flatten_image_paths: 把 image_paths JSON ({OD/OS/OU: [...]}) 拍平成图片列表
- mask_phone_by_role:  按角色对 phone 做脱敏（ADMIN 完整 / TEACHER 脱敏 / 其他隐藏）
"""
from typing import List, Optional, Tuple

from app.db.models.user import RoleEnum
from app.services.patient_mock import mask_phone


def flatten_image_paths(image_paths: Optional[dict]) -> List[str]:
    """把 image_paths JSON 拍平成有序 URL 列表（OD → OS → OU）"""
    if not isinstance(image_paths, dict):
        return []
    out: List[str] = []
    for side in ("OD", "OS", "OU"):
        arr = image_paths.get(side) or []
        if isinstance(arr, list):
            out.extend([p for p in arr if isinstance(p, str)])
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
