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


# --------------------------------------------------------------------------
# 结构化金标准推导
# --------------------------------------------------------------------------

class FakeCase:
    def __init__(self, category="DR", grade="3", lesions=None, anns=None):
        self.category = category
        self.gold_dr_grade = grade
        self.gold_lesions = lesions or []
        self.gold_annotations = anns or []


def test_gold_derived_from_existing_fields():
    """
    不要求教师重新录一遍：分级、病灶标签都已存在，
    处置按 DR 分级的通行随访间隔映射。
    """
    gold = df.gold_from_case(FakeCase(grade="3", lesions=[{"label": "微动脉瘤"}]))
    assert gold["dr_grade"] == "3"
    assert gold["disposition"] == "followup_3m"
    assert "MA" in gold["findings"]


def test_gold_maps_severity_to_followup_interval():
    assert df.gold_from_case(FakeCase(grade="0"))["disposition"] == "followup_12m"
    assert df.gold_from_case(FakeCase(grade="2"))["disposition"] == "followup_6m"
    assert df.gold_from_case(FakeCase(grade="4"))["disposition"] == "refer_urgent"


def test_gold_omits_grade_when_not_applicable():
    """
    金标准分级为空表示「不适用」，不能又推出一个具体分级——
    否则等于把之前修掉的「不适用变 0 级」问题重新引入。
    """
    gold = df.gold_from_case(FakeCase(category="GLAUCOMA", grade=""))
    assert "dr_grade" not in gold


def test_gold_collects_findings_from_annotations():
    gold = df.gold_from_case(FakeCase(anns=[{"label": "硬性渗出"}, {"label": "出血"}]))
    assert set(gold["findings"]) >= {"EX", "HE"}


# --------------------------------------------------------------------------
# 结构化评分
# --------------------------------------------------------------------------

def test_perfect_structured_answer_scores_full():
    gold = {"findings": ["MA", "HE"], "disposition": "followup_6m"}
    r = df.score_structured("DR", dict(gold), gold)
    assert r["score"] == 100.0
    assert r["errors"] == []


def test_missing_finding_is_reported():
    gold = {"findings": ["MA", "HE"], "disposition": "followup_6m"}
    r = df.score_structured("DR", {"findings": ["MA"], "disposition": "followup_6m"}, gold)
    assert r["score"] < 100
    assert any("漏报" in e for e in r["errors"])


def test_extra_finding_is_penalized():
    """多报同样要扣分，否则学员会倾向于全选"""
    gold = {"findings": ["MA"], "disposition": "routine"}
    r = df.score_structured("DR", {"findings": ["MA", "NV"], "disposition": "routine"}, gold)
    assert r["score"] < 100
    assert any("多报" in e for e in r["errors"])


def test_disposition_is_all_or_nothing():
    """处置直接关系患者去向，没有部分正确"""
    gold = {"disposition": "refer_urgent"}
    r = df.score_structured("DR", {"disposition": "routine"}, gold)
    assert r["detail"]["disposition"] == 0.0
    assert any("处置" in e for e in r["errors"])


def test_wrong_disposition_reported_even_if_findings_right():
    """关键词匹配区分不出「征象对但处置错」，结构化必须能"""
    gold = {"findings": ["MA"], "disposition": "refer_urgent"}
    r = df.score_structured("DR", {"findings": ["MA"], "disposition": "routine"}, gold)
    assert r["detail"]["findings"] == 100.0
    assert r["detail"]["disposition"] == 0.0


def test_gold_reads_type_key_from_imported_data():
    """
    金标准里病灶键名不统一：导入数据用 type，教师手工标注用 label。
    只认 label 会让导入的病例全部推不出征象，
    进而把学员的正确作答判成「多报」。
    """
    case = FakeCase(lesions=[{"type": "MA", "pixel_count": 6941},
                             {"type": "HE", "pixel_count": 35430}])
    gold = df.gold_from_case(case)
    assert set(gold["findings"]) == {"MA", "HE"}


def test_zero_pixel_lesion_is_not_a_finding():
    """pixel_count 为 0 表示该类病灶实际不存在，不应算作征象"""
    case = FakeCase(lesions=[{"type": "MA", "pixel_count": 100},
                             {"type": "SE", "pixel_count": 0}])
    gold = df.gold_from_case(case)
    assert "MA" in gold["findings"]
    assert "SE" not in gold["findings"]


def test_no_lesion_data_means_findings_not_scored():
    """
    金标准没记录征象 ≠ 该病例没有征象。
    把「未知」当成「无」，会把学员的正确作答全判成「多报」——
    这与「不适用被当成 0 级」是同一类错误。
    """
    gold = df.gold_from_case(FakeCase(lesions=[], anns=[]))
    assert "findings" not in gold

    r = df.score_structured("DR", {"findings": ["MA", "HE"]}, gold)
    assert not any("多报" in e for e in r["errors"])


def test_findings_scored_only_when_gold_has_data():
    """有金标准征象数据时才参与评分"""
    gold = df.gold_from_case(FakeCase(lesions=[{"type": "MA", "pixel_count": 5}]))
    r = df.score_structured("DR", {"findings": ["MA", "NV"]}, gold)
    assert any("多报：NV" in e or "多报征象：NV" in e for e in r["errors"])


def _dme_field(form):
    return next(field for field in form["fields"] if field["key"] == "dme")


def test_fundus_photo_cannot_diagnose_center_involved_dme():
    form = df.get_form("DR")
    field = _dme_field(form)
    labels = " ".join(item["label"] for item in field["options"])
    assert "中心受累黄斑水肿" not in labels
    assert "临床显著性" not in labels
    assert "OCT" in field["hint"]
    assert "分开" in field["hint"]
    grade = next(item for item in form["fields"] if item["key"] == "dr_grade")
    assert grade["hint"]
    assert df.dme_answer_problem({"dme": "csme"})
    assert df.dme_answer_problem({"dme": "center"})
    assert df.dme_answer_problem({"dme": "not_from_photo"}) == ""


def test_center_dme_opens_only_when_oct_and_visual_acuity_both_exist():
    photo = df.get_form("DR", {"has_oct": True, "has_visual_acuity": False})
    assert "center" not in {item["value"] for item in _dme_field(photo)["options"]}
    ready = df.get_form("DR", {"has_oct": True, "has_visual_acuity": True})
    assert {item["value"] for item in _dme_field(ready)["options"]} == {
        "none", "non_center", "center",
    }
    assert df.dme_answer_problem(
        {"dme": "center"},
        {"has_oct": True, "has_visual_acuity": True},
    ) == ""
    assert df.dme_answer_problem(
        {"dme": "center"},
        {"has_oct": True, "has_visual_acuity": False},
    )


def test_visual_acuity_needs_a_number_and_octa_is_not_oct():
    assert df._text_has_visual_acuity("视力下降 6 月") is False
    assert df._text_has_visual_acuity("视力 0.3") is True
    assert df._text_has_oct("已做 OCTA") is False
    assert df._text_has_oct("OCT 中心子域增厚") is True


def test_gold_does_not_infer_dme_from_grade_or_exudate():
    gold = df.gold_from_case(FakeCase(
        grade="4",
        lesions=[{"type": "EX", "pixel_count": 8000}, {"label": "硬性渗出"}],
    ))
    assert "dme" not in gold
    scored = df.score_structured("DR", {"dme": "center", "findings": ["EX"]}, gold)
    assert "dme" not in scored["detail"]
    separate = df.score_structured(
        "DR",
        {"dme": "none", "findings": ["EX"]},
        {"dme": "center", "findings": ["EX"]},
    )
    assert separate["detail"]["dme"] == 0.0
    assert any("黄斑水肿" in item for item in separate["errors"])
    assert separate["detail"]["findings"] == 100.0
