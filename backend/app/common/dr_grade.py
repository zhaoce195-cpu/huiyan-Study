# -*- coding: utf-8 -*-
"""
DR 分级取值语义

对应《医学培训端评估与工作流重构报告》P1：
    「非 DR 病例仍显示『0 级无 DR』，把『不适用』误表达为『0 级』。」

语义约定
    '0'~'4'  已完成 DR 分级（'0' 表示确实无 DR，是有意义的结论）
    ''/None  DR 分级不适用（青光眼、AMD 等非 DR 病种，本就不做 DR 分级）

「不适用」与「0 级无 DR」是两个完全不同的结论：
前者表示这道题不该问，后者表示问了且答案是没有病变。
二者混同会让学员误以为非 DR 病例都是正常眼底。
"""

from typing import Optional

DR_GRADE_TEXT = {
    "0": "0 级 无 DR",
    "1": "1 级 轻度 NPDR",
    "2": "2 级 中度 NPDR",
    "3": "3 级 重度 NPDR",
    "4": "4 级 PDR（增殖性）",
}

NOT_APPLICABLE_TEXT = "不适用"

# 这些病种不做 DR 分级；DR 与 NORMAL 例外：
#   DR     —— 本就是 DR 病例
#   NORMAL —— 正常眼底，「0 级无 DR」是有意义的结论，不能改成不适用
NON_DR_CATEGORIES = frozenset({"AMD", "GLAUCOMA", "HYPERTENSION", "OTHER"})


def is_applicable(raw: Optional[str]) -> bool:
    """该病例是否适用 DR 分级"""
    return bool((raw or "").strip())


def grade_code(raw: Optional[str]) -> Optional[str]:
    """归一化分级编码；不适用返回 None"""
    v = (raw or "").strip()
    return v if v else None


def grade_level(raw: Optional[str]) -> Optional[int]:
    """
    分级数值，供前端渲染。

    不适用返回 None——绝不回落成 0，否则又会把「不适用」显示成「0 级无 DR」。
    """
    v = (raw or "").strip()
    if not v or not v.isdigit():
        return None
    n = int(v)
    return n if 0 <= n <= 4 else None


def grade_text(raw: Optional[str]) -> str:
    """分级中文名；不适用时明确返回「不适用」"""
    v = (raw or "").strip()
    if not v:
        return NOT_APPLICABLE_TEXT
    return DR_GRADE_TEXT.get(v, "")


def should_be_not_applicable(category: Optional[str], raw: Optional[str]) -> bool:
    """
    判断一条存量数据是否属于「被误标为 0 级的不适用病例」。

    仅当同时满足才判定，避免误伤真实分级：
        1. 病种属于不做 DR 分级的类别；
        2. 当前值是默认的 '0'（若为 1~4，说明有人确实分过级，保留）。
    """
    cat = (category or "").strip().upper()
    val = (raw or "").strip()
    return cat in NON_DR_CATEGORIES and val == "0"
