# -*- coding: utf-8 -*-
"""演示正文：病灶中文名按数据来源区分，非 DR 不说成 0 级。"""
from app.services.teaching_service import grade_line, lesion_rows


def test_idrid_pixels_call_he_hemorrhage():
    rows = lesion_rows([
        {"type": "MA", "pixel_count": 10},
        {"type": "HE", "pixel_count": 20},
        {"type": "EX", "pixel_count": 30},
    ])
    assert [r["name"] for r in rows] == ["微动脉瘤", "出血", "硬性渗出"]
    assert all(r["detail"] == "着色图里有这块区域" for r in rows)


def test_seed_counts_call_he_hard_exudate():
    rows = lesion_rows([
        {"type": "HM", "count": 5},
        {"type": "HE", "count": 3},
        {"type": "MA", "count": 0},
    ])
    assert rows[0]["name"] == "出血"
    assert rows[0]["detail"] == "约 5 处"
    assert rows[1]["name"] == "硬性渗出"
    assert rows[2]["detail"] == ""


def test_stringified_empty_annotations_are_not_a_lesion():
    assert lesion_rows("[]") == []
    assert lesion_rows(None) == []


def test_glaucoma_zero_is_not_dr_grade():
    assert grade_line("GLAUCOMA", "0") == "本例不按 DR 分级"


def test_dr_three_keeps_grade_name():
    assert grade_line("DR", "3") == "3 级 重度 NPDR"
