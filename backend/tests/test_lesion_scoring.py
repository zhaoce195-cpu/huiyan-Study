# -*- coding: utf-8 -*-
"""小病灶看找对、漏标、多标；出血和渗出看范围；串珠、IRMA、新生血管看象限。

只覆盖新一次提交会走到的 _score。不读取、不改写已经存下来的练习成绩。
"""

from app.schemas.practice import Point2D, PracticeAnnotation
from app.services.practice_service import _score
from tests.test_dr_grade import FakeCase


def _gold(label, x, y, w, h):
    return {"type": "rect", "label": label, "x": x, "y": y, "w": w, "h": h}


def _mark(label, points, remark="", tool="rect"):
    return PracticeAnnotation(
        id="S",
        tool=tool,
        label=label,
        layer="finding",
        remark=remark,
        points=[Point2D(x=p[0], y=p[1]) for p in points],
    )


def _run(gold, marks, image_size=(1000, 1000), eye="OD"):
    case = FakeCase("2")
    case.gold_annotations = gold
    result, errors = _score(
        case, "2", case.gold_diagnosis, marks,
        image_size=image_size, eye=eye,
    )
    return result, errors


def test_microaneurysm_near_miss_is_a_hit_without_overlap_penalty():
    """点在微动脉瘤附近就算找对，不因为圈没有重合而扣分。"""
    result, errors = _run(
        [_gold("微动脉瘤", 100, 100, 12, 12)],
        [_mark("微动脉瘤", [(130, 106)], remark="MA", tool="point")],
    )
    assert result["score_annotation"] == 100.0
    assert result["iou_avg"] < 0
    assert [e.type for e in errors] == []


def test_extra_microaneurysm_is_counted_apart_from_a_hit():
    result, errors = _run(
        [_gold("微动脉瘤", 100, 100, 12, 12)],
        [
            _mark("微动脉瘤", [(106, 106)], remark="MA", tool="point"),
            _mark("微动脉瘤", [(800, 800)], remark="MA", tool="point"),
        ],
    )
    assert result["score_annotation"] == 50.0
    assert result["false_positive_count"] == 1
    assert any(e.type == "false_positive" for e in errors)
    assert not any(e.type == "low_iou" for e in errors)


def test_missed_microaneurysm_lowers_the_score():
    result, errors = _run(
        [
            _gold("微动脉瘤", 100, 100, 12, 12),
            _gold("微动脉瘤", 400, 400, 12, 12),
        ],
        [_mark("微动脉瘤", [(106, 106)], remark="MA", tool="point")],
    )
    assert result["score_annotation"] == 50.0
    assert result["missed_count"] == 1
    assert any("漏标" in e.note for e in errors)


def test_closer_microaneurysm_keeps_the_mark():
    """一个点同时靠近两处时，归给更近的那处，另一处算漏标。"""
    result, errors = _run(
        [
            _gold("微动脉瘤", 100, 100, 10, 10),
            _gold("微动脉瘤", 130, 100, 10, 10),
        ],
        [_mark("微动脉瘤", [(132, 105)], remark="MA", tool="point")],
    )
    missed = [e for e in errors if e.type == "missed"]
    assert result["score_annotation"] == 50.0
    assert len(missed) == 1
    assert missed[0].point.x == 100


def test_small_hemorrhage_is_hit_or_miss_not_overlap_area():
    """和小微动脉瘤一样大的出血，不按重合面积给部分分。"""
    result, errors = _run(
        [_gold("出血", 100, 100, 20, 20)],
        [_mark("出血", [(115, 100), (135, 120)], remark="HE")],
    )
    assert result["score_annotation"] == 100.0
    assert result["iou_avg"] < 0
    assert not any(e.type == "low_iou" for e in errors)


def test_microaneurysm_alias_uses_the_same_hit_rule():
    result, errors = _run(
        [_gold("微血管瘤", 100, 100, 12, 12)],
        [_mark("微动脉瘤", [(130, 106)], remark="MA", tool="point")],
    )
    assert result["score_annotation"] == 100.0
    assert errors == []


def test_hemorrhage_scores_by_closeness_not_perfect_overlap():
    result, errors = _run(
        [_gold("出血", 0, 0, 100, 100)],
        [_mark("出血", [(0, 0), (60, 100)], remark="HE")],
    )
    assert result["score_annotation"] == 100.0
    assert result["iou_avg"] == 1.0
    assert not any(e.type == "low_iou" for e in errors)


def test_hemorrhage_partial_overlap_is_only_partly_credited():
    result, errors = _run(
        [_gold("出血", 0, 0, 100, 100)],
        [_mark("出血", [(0, 0), (30, 100)], remark="HE")],
    )
    assert result["score_annotation"] == round(100.0 * (0.3 / 0.45), 2)
    assert any(e.type == "low_iou" for e in errors)
    assert 0 < result["iou_avg"] < 1


def test_hard_and_soft_exudate_are_not_the_same_lesion():
    result, errors = _run(
        [_gold("硬性渗出", 0, 0, 80, 80)],
        [_mark("软性渗出", [(0, 0), (80, 80)], remark="SE")],
    )
    assert result["score_annotation"] == 0.0
    assert {e.type for e in errors} == {"missed", "false_positive"}


def test_exudate_alias_matches_hard_exudate():
    result, errors = _run(
        [_gold("渗出", 0, 0, 80, 80)],
        [_mark("硬性渗出", [(0, 0), (80, 80)], remark="EX")],
    )
    assert result["score_annotation"] == 100.0
    assert errors == []


def test_place_lesions_match_quadrant_not_box_overlap():
    gold = {
        "VB": _gold("静脉串珠", 100, 100, 40, 40),
        "IRMA": _gold("IRMA", 100, 100, 40, 40),
        "NV": _gold("新生血管", 100, 100, 40, 40),
    }
    labels = {"VB": "静脉串珠", "IRMA": "IRMA", "NV": "新生血管"}
    for code, box in gold.items():
        hit, hit_errors = _run(
            [box],
            [_mark(labels[code], [(80, 80)], remark=f"{code}:TS", tool="quadrant")],
        )
        miss, miss_errors = _run(
            [box],
            [_mark(labels[code], [(800, 800)], remark=f"{code}:NI", tool="quadrant")],
        )
        assert hit["score_annotation"] == 100.0, code
        assert hit["iou_avg"] < 0
        assert hit_errors == []
        assert miss["score_annotation"] == 0.0, code
        assert {e.type for e in miss_errors} == {"missed", "false_positive"}
