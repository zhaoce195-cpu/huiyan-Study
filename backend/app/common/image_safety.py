# -*- coding: utf-8 -*-
"""
影像安全标识工具

对应《医学培训端评估与工作流重构报告》P0/P1：
    「阅片主界面没有持续显示 OD/OS、中文眼别、检查日期、模态、图像质量和方向信息」
    「影像与图层混算：医生无法确认是否完整阅完原始检查」
    「OD 元数据与文件名 OS 冲突 → 阻断并醒目提示，不静默取任一值」

本模块只负责「把安全标识算准并如实表达」，不负责渲染。
未知信息一律显式标为未知，绝不用默认值静默填充。
"""

import re
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# 眼别
# ---------------------------------------------------------------------------
EYE_TEXT = {
    "OD": "右眼",
    "OS": "左眼",
    "OU": "双眼",
}

UNKNOWN_EYE = "UNKNOWN"
UNKNOWN_EYE_TEXT = "眼别未知"

# 文件名中可识别的眼别线索（用于与元数据交叉校验）。
# IDRiD 视盘层文件名以 _OD 结尾，这个 OD 是视盘，不是右眼，不能拿来和眼别记录比。
_EYE_PATTERNS = [
    (re.compile(r"(?<![A-Za-z])OD(?![A-Za-z])", re.I), "OD"),
    (re.compile(r"(?<![A-Za-z])OS(?![A-Za-z])", re.I), "OS"),
    (re.compile(r"(?<![A-Za-z])OU(?![A-Za-z])", re.I), "OU"),
    (re.compile(r"right[\-_ ]?eye|_r(?![A-Za-z])", re.I), "OD"),
    (re.compile(r"left[\-_ ]?eye|_l(?![A-Za-z])", re.I), "OS"),
    (re.compile(r"右眼"), "OD"),
    (re.compile(r"左眼"), "OS"),
    (re.compile(r"双眼"), "OU"),
]


def eye_text(eye: Optional[str]) -> str:
    """眼别中文名；未知时明确返回「眼别未知」而不是留空"""
    code = (eye or "").strip().upper()
    return EYE_TEXT.get(code, UNKNOWN_EYE_TEXT)


_IDRID_DISC_FILE = re.compile(r"(?i)^IDRiD_\d+_OD\.(png|tif|tiff)$")
_DISC_SUFFIX = re.compile(r"(?i)([_\-])OD(?=\.[A-Za-z0-9]+$)")


def _name_for_eye_check(file_name: str, role: str = "") -> str:
    """视盘层文件名末尾的 _OD 是图层名，先去掉再认眼别。"""
    name = file_name or ""
    base = name.replace("\\", "/").rsplit("/", 1)[-1]
    if (role or "").strip().upper() == "OD" or _IDRID_DISC_FILE.match(base):
        return _DISC_SUFFIX.sub("", name, count=1)
    return name


def eye_from_filename(file_name: str, *, role: str = "") -> Optional[str]:
    """从文件名推断眼别；无法判断时返回 None（不猜）"""
    name = _name_for_eye_check(file_name, role)
    if not name:
        return None
    for pattern, code in _EYE_PATTERNS:
        if pattern.search(name):
            return code
    return None


def detect_laterality_conflict(
    *, eye: Optional[str], file_name: str, role: str = "",
) -> Optional[str]:
    """
    交叉校验元数据眼别与文件名线索。

    冲突时返回描述文本，由上层决定阻断或醒目提示；
    一致或无法判断时返回 None。绝不静默采用其中一个值。
    """
    meta_eye = (eye or "").strip().upper()
    if meta_eye not in EYE_TEXT:
        return None

    name_eye = eye_from_filename(file_name, role=role)
    if not name_eye or name_eye == meta_eye:
        return None

    # OU 与单眼线索并存不算冲突（双眼图里出现 OD/OS 字样是常见命名）
    if meta_eye == "OU" or name_eye == "OU":
        return None

    return (
        f"眼别冲突：记录为 {meta_eye}（{EYE_TEXT[meta_eye]}），"
        f"但文件名提示 {name_eye}（{EYE_TEXT[name_eye]}）"
    )


# ---------------------------------------------------------------------------
# 影像角色：区分原始影像与派生对象
# ---------------------------------------------------------------------------
ROLE_TEXT = {
    "original": "原始影像",
    "MA": "微动脉瘤标注层",
    "HE": "出血标注层",
    "EX": "硬性渗出标注层",
    "SE": "软性渗出标注层",
    "OD": "视盘标注层",
    "color_mask": "彩色掩码",
    "overlay": "叠加图",
    "class_mask": "分类掩码",
    "heatmap": "AI 热力图",
    "other": "其他",
}

ORIGINAL_ROLE = "original"

# 派生对象：不属于「原始检查」，不应计入原图张数
DERIVED_ROLES = set(ROLE_TEXT) - {ORIGINAL_ROLE, "other"}


def role_text(role: Optional[str]) -> str:
    return ROLE_TEXT.get((role or "").strip(), "未知类型")


def is_original(role: Optional[str]) -> bool:
    return (role or "").strip() == ORIGINAL_ROLE


# ---------------------------------------------------------------------------
# 模态与质量
# ---------------------------------------------------------------------------
# 当前平台仅处理眼底彩照；接入 OCT/OCTA 后应改为按影像实际模态判定，
# 而不是继续沿用这个常量。
DEFAULT_MODALITY = "CFP"
DEFAULT_MODALITY_TEXT = "眼底彩照"

QUALITY_TEXT = {
    "good": "优质",
    "usable": "可用",
    "poor": "较差",
    "ungradable": "不可判读",
}
UNKNOWN_QUALITY = "unknown"
UNKNOWN_QUALITY_TEXT = "未评估"


def quality_text(quality: Optional[str]) -> str:
    return QUALITY_TEXT.get((quality or "").strip().lower(), UNKNOWN_QUALITY_TEXT)


def is_ungradable(quality: Optional[str]) -> bool:
    """
    是否属于不可判读。

    报告要求：低质量图不得默认按正常处理，必须支持不可判读并进入重拍/转诊流程。
    """
    return (quality or "").strip().lower() in ("poor", "ungradable")


# ---------------------------------------------------------------------------
# 组装安全元数据
# ---------------------------------------------------------------------------

def build_image_meta(
    *,
    records: Optional[List[Any]] = None,
    legacy: Optional[List[Dict[str, Any]]] = None,
    quality_map: Optional[Dict[int, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    生成带安全标识的影像元数据列表。

    :param records:     CaseImage ORM 记录（新表，含 eye / role / file_name）
    :param legacy:      老 image_paths 平铺结果（{index, url, side}）
    :param quality_map: {case_image_id: CaseImageQuality}，缺失即「未评估」
    :return: 每张影像一条，含眼别、类型、是否原图、质量、冲突提示与序号
    """
    quality_map = quality_map or {}
    out: List[Dict[str, Any]] = []

    if records:
        for r in records:
            eye = (getattr(r, "eye", "") or "").upper()
            role = getattr(r, "role", "") or ""
            file_name = getattr(r, "file_name", "") or ""
            conflict = detect_laterality_conflict(
                eye=eye, file_name=file_name, role=role,
            )
            q = quality_map.get(getattr(r, "id", None))
            q_code = (getattr(q, "quality", None) or UNKNOWN_QUALITY) if q else UNKNOWN_QUALITY
            out.append({
                "url": getattr(r, "file_url", "") or "",
                "fileName": file_name,
                "eye": eye or UNKNOWN_EYE,
                "eyeText": eye_text(eye),
                "role": role,
                "roleText": role_text(role),
                "isOriginal": is_original(role),
                "quality": q_code,
                "qualityText": quality_text(q_code),
                "qualityConfidence": float(getattr(q, "confidence", 0.0) or 0.0) if q else 0.0,
                "ungradable": is_ungradable(q_code),
                "lateralityConflict": conflict,
            })
    elif legacy:
        for m in legacy:
            eye = (m.get("side") or "").upper()
            out.append({
                "url": m.get("url", ""),
                "fileName": "",
                "eye": eye or UNKNOWN_EYE,
                "eyeText": eye_text(eye),
                "role": ORIGINAL_ROLE,
                "roleText": role_text(ORIGINAL_ROLE),
                "isOriginal": True,
                "quality": UNKNOWN_QUALITY,
                "qualityText": UNKNOWN_QUALITY_TEXT,
                "qualityConfidence": 0.0,
                "ungradable": False,
                "lateralityConflict": None,
            })

    # 序号：原图与派生对象分别编号，避免「8 张影像」把两类混算
    original_total = sum(1 for m in out if m["isOriginal"])
    oi = 0
    for i, m in enumerate(out):
        m["index"] = i
        if m["isOriginal"]:
            oi += 1
            m["originalIndex"] = oi
            m["originalTotal"] = original_total
        else:
            m["originalIndex"] = None
            m["originalTotal"] = original_total

    return out


def summarize_safety(meta: List[Dict[str, Any]]) -> Dict[str, Any]:
    """汇总病例级安全标识，供安全条一次性展示"""
    originals = [m for m in meta if m.get("isOriginal")]
    eyes = sorted({m["eye"] for m in originals if m.get("eye") in EYE_TEXT})
    conflicts = [m["lateralityConflict"] for m in meta if m.get("lateralityConflict")]
    ungradable = [m for m in originals if m.get("ungradable")]
    unevaluated = [m for m in originals
                   if (m.get("quality") or UNKNOWN_QUALITY) == UNKNOWN_QUALITY]
    return {
        "originalCount": len(originals),
        "derivedCount": len(meta) - len(originals),
        "ungradableCount": len(ungradable),
        "unevaluatedCount": len(unevaluated),
        "hasUngradable": bool(ungradable),
        "qualityChecked": len(unevaluated) == 0 and bool(originals),
        "eyes": eyes,
        "eyesText": "、".join(eye_text(e) for e in eyes) if eyes else UNKNOWN_EYE_TEXT,
        "hasLateralityConflict": bool(conflicts),
        "lateralityConflicts": conflicts,
    }
