# -*- coding: utf-8 -*-
"""
结构化诊断表单测试

对应《医学培训端评估与工作流重构报告》：
    P1「阅片提交只有自由备注，结论难评分、难审计、难统计」
    P0「先质量后诊断：不可判读时不能默认为正常」
    5.1「不要用单一 DR 量表覆盖青光眼、AMD 等病种」
"""

import pytest

from app.common import diagnosis_form as df


# --------------------------------------------------------------------------
# 表单结构
# --------------------------------------------------------------------------

def test_quality_field_comes_first():
    """可判读性必须排在最前——先质量后诊断"""
    form = df.get_form("DR")
    assert form["fields"][0]["key"] == "readability"


def test_field_order_follows_report():
    """质量 → 分级/征象 → 置信度 → 处置 → 备注"""
    keys = [f["key"] for f in df.get_form("DR")["fields"]]
    assert keys.index("readability") < keys.index("dr_grade")
    assert keys.index("dr_grade") < keys.index("confidence")
    assert keys.index("confidence") < keys.index("disposition")
    assert keys[-1] == "note"


@pytest.mark.parametrize("category,expected_key", [
    ("DR", "dr_grade"),
    ("GLAUCOMA", "cdr"),
    ("AMD", "amd_type"),
])
def test_forms_are_category_specific(category, expected_key):
    """
    报告 5.1：表单必须病种特异，不能用一套 DR 量表覆盖所有病种。
    """
    keys = [f["key"] for f in df.get_form(category)["fields"]]
    assert expected_key in keys


def test_glaucoma_form_has_no_dr_grade():
    """青光眼表单里不应出现 DR 分级"""
    keys = [f["key"] for f in df.get_form("GLAUCOMA")["fields"]]
    assert "dr_grade" not in keys


def test_unknown_category_falls_back_to_generic_not_dr():
    """
    未登记病种回退到通用结论，而不是套用 DR 量表——
    套用会诱导学员对非 DR 病例做 DR 分级。
    """
    form = df.get_form("SOMETHING_NEW")
    keys = [f["key"] for f in form["fields"]]
    assert form["categoryKnown"] is False
    assert "dr_grade" not in keys
    assert "impression" in keys


def test_note_is_supplementary_not_required():
    """自由文本只作补充，不能替代结构化结论"""
    note = [f for f in df.get_form("DR")["fields"] if f["key"] == "note"][0]
    assert note["required"] is False


# --------------------------------------------------------------------------
# 校验：常规路径
# --------------------------------------------------------------------------

def _valid_dr():
    return {
        "readability": "readable",
        "dr_grade": "2",
        "confidence": "high",
        "disposition": "followup_6m",
    }


def test_complete_answer_passes():
    assert df.validate("DR", _valid_dr()) == []


@pytest.mark.parametrize("missing", ["readability", "dr_grade", "confidence", "disposition"])
def test_missing_required_field_is_reported(missing):
    answers = _valid_dr()
    answers.pop(missing)
    problems = df.validate("DR", answers)
    assert problems, f"缺少 {missing} 却未被拦截"


def test_empty_answer_lists_every_missing_field():
    problems = df.validate("DR", {})
    assert len(problems) >= 4


def test_empty_string_counts_as_missing():
    answers = _valid_dr()
    answers["dr_grade"] = ""
    assert df.validate("DR", answers)


# --------------------------------------------------------------------------
# 不可判读：报告 P0 的核心语义
# --------------------------------------------------------------------------

def test_ungradable_does_not_require_grading():
    """
    不可判读时再逼学员填分级与征象没有意义，
    还会诱导他对着看不清的图硬猜。
    """
    problems = df.validate("DR", {
        "readability": "ungradable",
        "disposition": "retake",
    })
    assert problems == []


def test_ungradable_rejects_negative_grade():
    """
    不可判读却给出「0 级 无 DR」——这正是报告 P0 要防的
    「低质量图被当成正常」。
    """
    problems = df.validate("DR", {
        "readability": "ungradable",
        "dr_grade": "0",
        "disposition": "retake",
    })
    assert any("阴性" in p for p in problems)


def test_ungradable_rejects_routine_followup():
    """不可判读还只做常规随访，等于把问题放过去"""
    problems = df.validate("DR", {
        "readability": "ungradable",
        "disposition": "routine",
    })
    assert any("重新拍摄" in p or "转诊" in p for p in problems)


def test_ungradable_accepts_retake_or_referral():
    for disposition in ("retake", "refer", "refer_urgent"):
        assert df.validate("DR", {
            "readability": "ungradable",
            "disposition": disposition,
        }) == []


def test_readable_still_requires_full_answer():
    """可判读时不能借「不可判读」的宽松规则绕过必填"""
    problems = df.validate("DR", {
        "readability": "readable",
        "disposition": "routine",
    })
    assert problems


# --------------------------------------------------------------------------
# 表单元数据
# --------------------------------------------------------------------------

def test_skip_list_excludes_always_required_fields():
    """不可判读时仍需填处置；可判读性本身当然也要保留"""
    form = df.get_form("DR")
    assert "readability" not in form["skipWhenUngradable"]
    assert "disposition" not in form["skipWhenUngradable"]
    assert "dr_grade" in form["skipWhenUngradable"]


def test_every_field_has_label_and_type():
    for category in ("DR", "GLAUCOMA", "AMD", "OTHER"):
        for f in df.get_form(category)["fields"]:
            assert f.get("label"), f"{category}/{f['key']} 缺 label"
            assert f.get("type"), f"{category}/{f['key']} 缺 type"


def test_option_fields_have_options():
    for category in ("DR", "GLAUCOMA", "AMD"):
        for f in df.get_form(category)["fields"]:
            if f["type"] in ("select", "radio", "checkbox"):
                assert f.get("options"), f"{category}/{f['key']} 缺 options"
