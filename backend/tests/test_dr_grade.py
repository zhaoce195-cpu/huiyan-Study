# -*- coding: utf-8 -*-
"""
DR 分级「不适用」与「0 级无 DR」的区分

对应《医学培训端评估与工作流重构报告》P1：
    「非 DR 病例仍显示『0 级无 DR』，把『不适用』误表达为『0 级』。」
"""

import pytest

from app.common.dr_grade import (
    NON_DR_CATEGORIES,
    NOT_APPLICABLE_TEXT,
    grade_code,
    grade_level,
    grade_text,
    is_applicable,
    should_be_not_applicable,
)


# --------------------------------------------------------------------------
# 取值语义
# --------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("0", 0), ("1", 1), ("2", 2), ("3", 3), ("4", 4),
])
def test_graded_cases_keep_level(raw, expected):
    assert grade_level(raw) == expected
    assert is_applicable(raw) is True


@pytest.mark.parametrize("raw", ["", "   ", None])
def test_not_applicable_is_none_never_zero(raw):
    """
    这是本次修复的核心：不适用必须是 None。
    一旦回落成 0，界面就会把「不做 DR 分级」显示成「0 级无 DR」。
    """
    assert grade_level(raw) is None
    assert grade_level(raw) != 0
    assert grade_code(raw) is None
    assert is_applicable(raw) is False


def test_zero_and_not_applicable_have_different_text():
    assert grade_text("0") == "0 级 无 DR"
    assert grade_text("") == NOT_APPLICABLE_TEXT
    assert grade_text("0") != grade_text("")


@pytest.mark.parametrize("raw", ["5", "9", "-1", "abc"])
def test_out_of_range_is_none(raw):
    """越界或非法值不猜测，一律 None"""
    assert grade_level(raw) is None


# --------------------------------------------------------------------------
# 回填判定
# --------------------------------------------------------------------------

@pytest.mark.parametrize("category", sorted(NON_DR_CATEGORIES))
def test_non_dr_category_with_default_zero_should_backfill(category):
    assert should_be_not_applicable(category, "0") is True


@pytest.mark.parametrize("category", sorted(NON_DR_CATEGORIES))
@pytest.mark.parametrize("grade", ["1", "2", "3", "4"])
def test_real_grade_is_never_touched(category, grade):
    """
    非 DR 病种若已被打上 1~4 级，说明有人确实分过级（如糖尿病合并青光眼），
    必须保留，不能当成误标清掉。
    """
    assert should_be_not_applicable(category, grade) is False


def test_dr_category_never_backfilled():
    """DR 病例的 0 级是有效结论"""
    for g in ["0", "1", "2", "3", "4"]:
        assert should_be_not_applicable("DR", g) is False


def test_normal_category_never_backfilled():
    """
    NORMAL（正常眼底）的「0 级无 DR」同样是有意义的结论，
    不属于「不适用」，不能一起清掉。
    """
    assert should_be_not_applicable("NORMAL", "0") is False


def test_already_backfilled_is_not_matched_again():
    """回填幂等：已经是空值的不会被再次命中"""
    assert should_be_not_applicable("AMD", "") is False
    assert should_be_not_applicable("AMD", None) is False


def test_category_case_insensitive():
    assert should_be_not_applicable("amd", "0") is True


# --------------------------------------------------------------------------
# 评分：不适用的病例不考分级题
# --------------------------------------------------------------------------

class FakeCase:
    """构造评分所需的最小病例对象"""

    def __init__(self, gold_dr_grade, gold_diagnosis="出血 渗出", pass_score=60):
        self.gold_dr_grade = gold_dr_grade
        self.gold_diagnosis = gold_diagnosis
        self.gold_annotations = []
        self.gold_lesions = []
        self.pass_score = pass_score


def _score_case(gold_grade, student_grade, diagnosis="出血 渗出"):
    from app.services.practice_service import _score
    result, _errors = _score(
        FakeCase(gold_grade), student_grade, diagnosis, [],
    )
    return result


def test_applicable_case_penalizes_wrong_grade():
    """常规 DR 病例：分级答错要扣分"""
    right = _score_case("3", "3")
    wrong = _score_case("3", "0")
    assert right["score_grade"] == 100.0
    assert wrong["score_grade"] < 100.0
    assert right["score_total"] > wrong["score_total"]


@pytest.mark.parametrize("student_answer", ["", "0", "3"])
def test_not_applicable_case_does_not_penalize_any_answer(student_answer):
    """
    分级不适用时，学员填什么都不该影响总分——
    否则非 DR 病例会变成「怎么答都扣分」。
    """
    base = _score_case("", "0")["score_total"]
    assert _score_case("", student_answer)["score_total"] == base


def test_not_applicable_case_redistributes_grade_weight():
    """
    分级不适用、又没有金标准框时，这两项都不考。
    总分就是诊断分，不能因为没考的项把满分压到 70。
    """
    r = _score_case("", "")
    assert r["score_grade"] == 0.0
    assert r["annotation_applicable"] is False
    assert r["score_total"] == r["score_diagnosis"]
    # 若不做权重重分配，诊断只占 20%，满分被压低
    naive = round(r["score_diagnosis"] * 0.2, 2)
    assert r["score_total"] > naive


def test_no_gold_annotation_no_longer_caps_the_score():
    """
    无金标准标注框、学员也没标：标注未考，不记 100。
    分级和诊断都对时，权重摊开后总分仍是 100。
    """
    r = _score_case("3", "3")
    assert r["annotation_applicable"] is False
    assert r["score_annotation"] == 0.0
    assert r["accuracy"] == 0.0
    assert r["score_grade"] == 100.0
    assert r["score_diagnosis"] == 100.0
    assert r["score_total"] == 100.0, "没考标注时，分级和诊断全对仍应满分"


# --------------------------------------------------------------------------
# 评分口径：新旧不得混用
# --------------------------------------------------------------------------

def test_legacy_free_text_keeps_keyword_scoring():
    """
    历史记录没有结构化作答，必须仍按关键词口径评分——
    否则历史成绩会被新口径悄悄重算，无法与当时的分数对比。
    """
    from app.services.practice_service import _score

    result, _ = _score(FakeCase("3"), "3", "出血 渗出", [], structured=None)
    assert result["scoring_mode"] == "keyword"


def test_structured_answer_switches_mode_explicitly():
    """有结构化作答时整题走结构化，并显式标记口径"""
    from app.services.practice_service import _score

    case = FakeCase("3")
    case.category = "DR"
    case.gold_lesions = [{"label": "微动脉瘤"}]
    result, _ = _score(
        case, "3", "",
        [],
        structured={"readability": "readable", "findings": ["MA"],
                    "disposition": "followup_3m"},
    )
    assert result["scoring_mode"] == "structured"
    assert result["score_diagnosis"] == 100.0


def test_two_modes_never_mix():
    """同一次作答只会用一种口径，不会把两种分数掺在一起"""
    from app.services.practice_service import _score

    case = FakeCase("3")
    case.category = "DR"
    case.gold_lesions = [{"label": "微动脉瘤"}]
    # 同时给自由文本与结构化：结构化优先，关键词不参与
    result, _ = _score(
        case, "3", "完全不相关的文字", [],
        structured={"readability": "readable", "findings": ["MA"],
                    "disposition": "followup_3m"},
    )
    assert result["scoring_mode"] == "structured"
    assert result["score_diagnosis"] == 100.0, "自由文本不应拉低结构化得分"


# --------------------------------------------------------------------------
# D-002 修正的边界：只放宽「无从度量」的情形，不放宽「答错」
# --------------------------------------------------------------------------

def _score_with_anns(gold_grade, student_grade, student_anns, gold_anns=None):
    from app.services.practice_service import _score
    from app.schemas.practice import PracticeAnnotation, Point2D
    case = FakeCase(gold_grade)
    case.gold_annotations = gold_anns or []
    anns = [
        PracticeAnnotation(
            id=f"S{i}", tool="rect", label=a["label"],
            points=[Point2D(x=a["x"], y=a["y"]),
                    Point2D(x=a["x"] + 50, y=a["y"] + 50)],
        )
        for i, a in enumerate(student_anns)
    ]
    result, _ = _score(case, student_grade, case.gold_diagnosis, anns)
    return result


def test_marking_lesions_on_a_clean_case_still_scores_zero():
    """
    无金标准框 ≠ 怎么标都给分。学员在没有病灶的图上乱标，
    仍是全部误报，标注分应为 0 —— 修正放宽的是「无从度量」，
    不是「答错」。
    """
    r = _score_with_anns("3", "3", [{"label": "出血", "x": 10, "y": 10}])
    assert r["score_annotation"] == 0.0


def test_missing_all_gold_lesions_still_scores_zero():
    """
    有金标准框但学员一个没标：同样是 iou_cnt == 0，
    但召回率为 0，标注分必须仍是 0，不能被新分支放行。
    """
    gold = [{"type": "rect", "label": "出血", "x": 10, "y": 10, "w": 40, "h": 40}]
    r = _score_with_anns("3", "3", [], gold_anns=gold)
    assert r["score_annotation"] == 0.0


def test_normal_case_with_no_marks_is_not_scored_as_perfect():
    """没有金标准框、学员也没标：标注未考，不能显示成 100 分答对"""
    r = _score_with_anns("3", "3", [])
    assert r["annotation_applicable"] is False
    assert r["score_annotation"] == 0.0
    assert r["accuracy"] == 0.0
