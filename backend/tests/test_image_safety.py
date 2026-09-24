# -*- coding: utf-8 -*-
"""
影像安全标识测试

覆盖《医学培训端评估与工作流重构报告》8.3 高价值回归用例：
    P0「OD 元数据与文件名 OS 冲突 → 阻断并醒目提示，不静默取任一值」
    P1「影像与图层混算 → 原图与派生对象分别计数」
    P0「低质量 / 遮挡 / 空白图 → 标记不可判读，不得默认阴性」
"""

import pytest

from app.common.image_safety import (
    build_image_meta,
    detect_laterality_conflict,
    eye_from_filename,
    eye_text,
    is_original,
    is_ungradable,
    quality_text,
    summarize_safety,
)


class FakeImage:
    """模拟 CaseImage ORM 记录"""

    def __init__(self, url, eye="OU", role="original", file_name=""):
        self.file_url = url
        self.eye = eye
        self.role = role
        self.file_name = file_name


# --------------------------------------------------------------------------
# 眼别
# --------------------------------------------------------------------------

@pytest.mark.parametrize("code,expected", [
    ("OD", "右眼"), ("OS", "左眼"), ("OU", "双眼"),
    ("od", "右眼"),
])
def test_eye_text_known(code, expected):
    assert eye_text(code) == expected


@pytest.mark.parametrize("code", [None, "", "XX", "LEFT"])
def test_eye_text_unknown_is_explicit(code):
    """未知眼别必须显式表达，不能返回空串让界面留白"""
    assert eye_text(code) == "眼别未知"


@pytest.mark.parametrize("name,expected", [
    ("IDRiD_01_OD.jpg", "OD"),
    ("patient_OS_20260101.png", "OS"),
    ("case-OU-fundus.tif", "OU"),
    ("scan_right_eye.jpg", "OD"),
    ("scan_left-eye.jpg", "OS"),
    ("张三_右眼_底片.jpg", "OD"),
])
def test_eye_from_filename(name, expected):
    assert eye_from_filename(name) == expected


@pytest.mark.parametrize("name", ["IDRiD_81.jpg", "fundus_001.png", ""])
def test_eye_from_filename_does_not_guess(name):
    """无线索时返回 None，绝不猜测"""
    assert eye_from_filename(name) is None


# --------------------------------------------------------------------------
# 眼别冲突（报告 8.3 首条 P0）
# --------------------------------------------------------------------------

def test_laterality_conflict_detected():
    """元数据 OD、文件名 OS → 必须报冲突"""
    msg = detect_laterality_conflict(eye="OD", file_name="patient_OS_001.jpg")
    assert msg
    assert "OD" in msg and "OS" in msg
    assert "右眼" in msg and "左眼" in msg


def test_optic_disc_filename_is_not_a_right_eye():
    """IDRiD 的 *_OD.png 是视盘层。记录为左眼时，不能把文件名报成右眼。"""
    assert eye_from_filename("IDRiD_81_OD.png", role="OD") is None
    assert detect_laterality_conflict(
        eye="OS", file_name="IDRiD_81_OD.png", role="OD",
    ) is None
    records = [
        FakeImage("/o.jpg", eye="OS", role="original", file_name="IDRiD_81.jpg"),
        FakeImage("/d.png", eye="OS", role="OD", file_name="IDRiD_81_OD.png"),
    ]
    meta = build_image_meta(records=records)
    assert meta[0]["lateralityConflict"] is None
    assert meta[1]["lateralityConflict"] is None
    assert summarize_safety(meta)["hasLateralityConflict"] is False
    assert detect_laterality_conflict(eye="OS", file_name="IDRiD_81_OD.png") is None


def test_laterality_conflict_reverse():
    msg = detect_laterality_conflict(eye="OS", file_name="scan_right_eye.png")
    assert msg


@pytest.mark.parametrize("eye,name", [
    ("OD", "case_OD_1.jpg"),      # 一致
    ("OS", "IDRiD_12.jpg"),       # 文件名无线索
    ("OU", "both_OD_OS.jpg"),     # 双眼图含单眼字样，属正常命名
    ("OD", "OU_montage.jpg"),     # 与双眼线索不算冲突
])
def test_no_false_conflict(eye, name):
    assert detect_laterality_conflict(eye=eye, file_name=name) is None


def test_conflict_never_silently_picks_a_side():
    """
    冲突提示必须同时给出两个来源的值，
    以确保调用方无法「静默取任一值」而不告知用户。
    """
    msg = detect_laterality_conflict(eye="OD", file_name="x_OS_y.jpg")
    assert msg.count("眼") >= 2


def test_conflict_surfaces_in_meta_and_summary():
    records = [
        FakeImage("/a.jpg", eye="OD", file_name="a_OS_1.jpg"),
        FakeImage("/b.jpg", eye="OS", file_name="b_OS_2.jpg"),
    ]
    meta = build_image_meta(records=records)
    assert meta[0]["lateralityConflict"]
    assert meta[1]["lateralityConflict"] is None

    summary = summarize_safety(meta)
    assert summary["hasLateralityConflict"] is True
    assert len(summary["lateralityConflicts"]) == 1


# --------------------------------------------------------------------------
# 原图与派生对象分别计数（报告 P1：8 张影像到底是什么）
# --------------------------------------------------------------------------

def test_original_and_derived_counted_separately():
    records = [
        FakeImage("/o1.jpg", eye="OD", role="original"),
        FakeImage("/o2.jpg", eye="OS", role="original"),
        FakeImage("/m1.png", eye="OD", role="MA"),
        FakeImage("/m2.png", eye="OD", role="HE"),
        FakeImage("/ov.png", eye="OD", role="overlay"),
    ]
    meta = build_image_meta(records=records)
    summary = summarize_safety(meta)

    assert summary["originalCount"] == 2, "原图应只算 original 角色"
    assert summary["derivedCount"] == 3, "mask / overlay 属派生对象"
    assert summary["eyesText"] == "右眼、左眼" or summary["eyesText"] == "左眼、右眼"


def test_original_index_is_independent_of_derived():
    """原图序号必须独立编号，否则「第 3 张 / 共 5 张」会把 mask 算进去"""
    records = [
        FakeImage("/o1.jpg", role="original"),
        FakeImage("/m1.png", role="MA"),
        FakeImage("/o2.jpg", role="original"),
    ]
    meta = build_image_meta(records=records)
    originals = [m for m in meta if m["isOriginal"]]

    assert [m["originalIndex"] for m in originals] == [1, 2]
    assert all(m["originalTotal"] == 2 for m in originals)
    assert meta[1]["originalIndex"] is None, "派生对象不参与原图编号"


def test_legacy_image_paths_still_produce_meta():
    """老病例（image_paths 结构）也必须有完整安全标识"""
    legacy = [
        {"index": 0, "url": "/x/od.jpg", "side": "OD"},
        {"index": 1, "url": "/x/os.jpg", "side": "OS"},
    ]
    meta = build_image_meta(legacy=legacy)
    assert len(meta) == 2
    assert meta[0]["eye"] == "OD" and meta[0]["eyeText"] == "右眼"
    assert all(m["isOriginal"] for m in meta)
    assert summarize_safety(meta)["originalCount"] == 2


def test_empty_input_is_safe():
    assert build_image_meta() == []
    s = summarize_safety([])
    assert s["originalCount"] == 0
    assert s["eyesText"] == "眼别未知"
    assert s["hasLateralityConflict"] is False


# --------------------------------------------------------------------------
# 图像质量与不可判读（报告 P0：不得默认阴性）
# --------------------------------------------------------------------------

@pytest.mark.parametrize("q,expected", [
    ("good", "优质"), ("usable", "可用"),
    ("poor", "较差"), ("ungradable", "不可判读"),
])
def test_quality_text(q, expected):
    assert quality_text(q) == expected


@pytest.mark.parametrize("q", [None, "", "unknown", "??"])
def test_quality_unknown_is_explicit(q):
    assert quality_text(q) == "未评估"


@pytest.mark.parametrize("q,expected", [
    ("poor", True), ("ungradable", True),
    ("good", False), ("usable", False),
    (None, False), ("unknown", False),
])
def test_is_ungradable(q, expected):
    assert is_ungradable(q) is expected


def test_unevaluated_quality_is_not_treated_as_good():
    """
    未评估 ≠ 合格。质量门控上线前，界面必须显示「未评估」，
    不能因为没有质量数据就当作图像可判读。
    """
    meta = build_image_meta(records=[FakeImage("/a.jpg")])
    assert meta[0]["quality"] == "unknown"
    assert meta[0]["qualityText"] == "未评估"
    assert not is_ungradable(meta[0]["quality"])


def test_role_classification():
    assert is_original("original") is True
    for r in ("MA", "HE", "EX", "SE", "overlay", "color_mask"):
        assert is_original(r) is False
