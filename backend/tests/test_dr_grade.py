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
    分级那 30% 应按比例分摊给标注与诊断，
    而不是让非 DR 病例的总分上限直接掉到 70。
    """
    r = _score_case("", "")
    # 分级不计分
    assert r["score_grade"] == 0.0
    # 总分 = 标注 * (0.5/0.7) + 诊断 * (0.2/0.7)
    expected = round(
        r["score_annotation"] * (0.5 / 0.7) + r["score_diagnosis"] * (0.2 / 0.7), 2,
    )
    assert r["score_total"] == expected
    # 若不做权重重分配，同样答卷只能拿到 0.5+0.2=70% 的分，明显偏低
    naive = round(r["score_annotation"] * 0.5 + r["score_diagnosis"] * 0.2, 2)
    assert r["score_total"] > naive


def test_known_issue_no_gold_annotation_caps_annotation_score_at_70():
    """
    【既有缺陷·固化现状，非本次引入】

    标注分公式为 accuracy * 70 + iou_avg * 30。
    当病例没有任何金标准标注（正常眼底、无病灶病例）时：
        accuracy = 1.0（没有漏标）
        iou_avg  = 0.0（没有框可算 IoU）
    → 标注分恒为 70，学员即使完全答对也拿不到满分，
      连带 DR 病例全对时总分只有 85。

    本测试用于固化该行为并使其可见；修复需要调整评分口径，
    会影响历史成绩可比性，应单独评估后再改。
    """
    r = _score_case("3", "3")
    assert r["score_annotation"] == 70.0
    assert r["score_grade"] == 100.0
    assert r["score_diagnosis"] == 100.0
    assert r["score_total"] == 85.0, "全对却拿不到满分，属既有评分缺陷"
