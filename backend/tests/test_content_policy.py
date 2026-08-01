# -*- coding: utf-8 -*-
"""
盲训内容策略契约测试

对应《医学培训端评估与工作流重构报告》验收门槛：
    「盲训隔离：提交前任何页面、URL、文件名、导出、接口响应都不返回金标准或答案型标签。」

本测试为 CI 阻断级：一旦失败即视为考核效度回归，不允许合并。
"""

import pytest

from app.core.content_policy import (
    ANSWER_FIELDS,
    PATH_FIELDS,
    ANSWER_FIELD_BLANKS,
    NEUTRALIZED_FIELDS,
    PresentationMode,
    SAFE_FIELDS,
    Scene,
    assert_no_answer_leak,
    is_blinded,
    redact,
    resolve_mode,
)
from app.schemas.case_browse import CaseBrowseDetail, CaseBrowseItem
from app.schemas.practice import CaseBriefForPractice


# --------------------------------------------------------------------------
# 1. 模式推导
# --------------------------------------------------------------------------

@pytest.mark.parametrize("scene", [Scene.CASE_BROWSE, Scene.PRACTICE, Scene.READING])
def test_student_unanswered_is_blinded(scene):
    """学员未作答 → 盲训态"""
    mode = resolve_mode(viewer_role="STUDENT", scene=scene, answered=False)
    assert mode is PresentationMode.TRAINING_BLINDED
    assert is_blinded(mode)


@pytest.mark.parametrize("scene", [Scene.CASE_BROWSE, Scene.PRACTICE, Scene.READING])
def test_student_answered_is_review(scene):
    """学员已提交 → 复盘态，答案解锁用于对照学习"""
    mode = resolve_mode(viewer_role="STUDENT", scene=scene, answered=True)
    assert mode is PresentationMode.TRAINING_REVIEW
    assert not is_blinded(mode)


@pytest.mark.parametrize("role", ["TEACHER", "ADMIN"])
def test_teacher_never_blinded(role):
    """教师与管理员需要看到答案才能备课、审核与点评"""
    mode = resolve_mode(viewer_role=role, scene=Scene.CASE_BROWSE, answered=False)
    assert mode is PresentationMode.TEACHING_DEMO
    assert not is_blinded(mode)


def test_unknown_role_defaults_to_blinded():
    """角色缺失或未知时，按最保守方式处理"""
    for role in (None, "", "GUEST", "PATIENT"):
        mode = resolve_mode(viewer_role=role, scene=Scene.PRACTICE, answered=False)
        assert is_blinded(mode), f"角色 {role!r} 未被判为盲态"


# --------------------------------------------------------------------------
# 2. 字段裁剪
# --------------------------------------------------------------------------

def _leaky_payload() -> dict:
    """构造一份「什么答案都带」的病例数据"""
    return {
        "id": 1,
        "case_no": "T2026001",
        "title": "糖尿病视网膜病变 DR 3 级 典型病例",
        "description": "重度 NPDR，可见大量出血与静脉串珠",
        "category": "DR",
        "category_text": "糖尿病视网膜病变",
        "difficulty": "HARD",
        "difficulty_text": "高级",
        "dr_level": 3,
        "dr_grade_text": "3 级 重度 NPDR",
        "gold_diagnosis": "重度非增殖性糖尿病视网膜病变",
        "teaching_points": "注意静脉串珠样改变",
        "gold_lesions": [{"label": "出血", "count": 12}],
        "clinical_info": "患者主诉视物模糊 3 月",
        "image_count": 4,
        "pass_score": 60,
    }


def test_blinded_removes_all_answer_fields():
    payload = _leaky_payload()
    out = redact(payload, PresentationMode.TRAINING_BLINDED, case_no="T2026001")

    assert out["dr_level"] is None
    assert out["dr_grade_text"] == ""
    assert out["gold_diagnosis"] == ""
    assert out["teaching_points"] == ""
    assert out["gold_lesions"] == []
    assert_no_answer_leak(out)


def test_blinded_neutralizes_title_and_description():
    """标题常含「DR 3 级」，直接清空会让列表不可用，应替换为中性标识"""
    out = redact(_leaky_payload(), PresentationMode.TRAINING_BLINDED, case_no="T2026001")
    assert out["title"] == "病例 T2026001"
    assert "DR" not in out["title"]
    assert "3 级" not in out["title"]
    assert out["description"] == ""


def test_blinded_keeps_learning_context():
    """盲态仍应保留学习目标类信息：难度、模态、影像数、通过线、临床输入"""
    out = redact(_leaky_payload(), PresentationMode.TRAINING_BLINDED, case_no="T2026001")
    assert out["difficulty"] == "HARD"
    assert out["difficulty_text"] == "高级"
    assert out["image_count"] == 4
    assert out["pass_score"] == 60
    assert out["clinical_info"] == "患者主诉视物模糊 3 月"
    assert out["case_no"] == "T2026001"


@pytest.mark.parametrize("mode", [
    PresentationMode.TRAINING_REVIEW,
    PresentationMode.TEACHING_DEMO,
    PresentationMode.CLINICAL,
])
def test_non_blinded_modes_keep_answers(mode):
    payload = _leaky_payload()
    out = redact(payload, mode, case_no="T2026001")
    assert out["dr_level"] == 3
    assert out["gold_diagnosis"] == "重度非增殖性糖尿病视网膜病变"
    assert out["title"] == payload["title"]


def test_redact_does_not_mutate_input():
    payload = _leaky_payload()
    redact(payload, PresentationMode.TRAINING_BLINDED, case_no="T2026001")
    assert payload["dr_level"] == 3, "redact 不得修改入参"


def test_mutable_blanks_are_not_shared():
    """列表型默认值必须复制，避免两次调用共享同一引用"""
    a = redact(_leaky_payload(), PresentationMode.TRAINING_BLINDED)
    b = redact(_leaky_payload(), PresentationMode.TRAINING_BLINDED)
    a["gold_lesions"].append("污染")
    assert b["gold_lesions"] == []


# --------------------------------------------------------------------------
# 3. 完整性守卫：新增字段必须显式归类，否则默认按答案处理
# --------------------------------------------------------------------------

CLASSIFIED = ANSWER_FIELDS | NEUTRALIZED_FIELDS | SAFE_FIELDS | PATH_FIELDS

GUARDED_MODELS = [CaseBrowseItem, CaseBrowseDetail, CaseBriefForPractice]


@pytest.mark.parametrize("model", GUARDED_MODELS, ids=lambda m: m.__name__)
def test_every_field_is_classified(model):
    """
    受保护模型的每个字段都必须在「答案 / 中性化 / 安全」三类之一中登记。

    新增字段若未归类，此测试即失败——等价于「默认按答案处理」，
    强制开发者在加字段时明确它是否属于答案。
    """
    unclassified = sorted(set(model.model_fields.keys()) - CLASSIFIED)
    assert not unclassified, (
        f"{model.__name__} 存在未归类字段 {unclassified}；"
        f"请在 app/core/content_policy.py 中登记为 ANSWER_FIELD_BLANKS、"
        f"NEUTRALIZED_FIELDS 或 SAFE_FIELDS"
    )


@pytest.mark.parametrize("model", GUARDED_MODELS, ids=lambda m: m.__name__)
def test_model_blinded_output_has_no_leak(model):
    """把模型默认实例过一遍盲态裁剪，确保不残留答案值"""
    instance = model(id=1, case_id=1, case_no="T2026001")
    out = redact(instance.model_dump(), PresentationMode.TRAINING_BLINDED,
                 case_no="T2026001")
    assert_no_answer_leak(out)


def test_answer_and_safe_sets_do_not_overlap():
    """同一字段不能既是答案又是安全字段"""
    overlap = (ANSWER_FIELDS | NEUTRALIZED_FIELDS) & SAFE_FIELDS
    assert not overlap, f"字段分类冲突：{sorted(overlap)}"


def test_dr_level_blank_is_none_not_zero():
    """
    报告 P1：非 DR 病例仍显示「0 级无 DR」，把「不适用」误表达为「0 级」。
    因此盲态与不适用都必须是 None，绝不能回落成 0。
    """
    assert ANSWER_FIELD_BLANKS["dr_level"] is None
    assert ANSWER_FIELD_BLANKS["dr_level"] != 0


def test_neutralized_fields_are_driven_by_the_registry():
    """
    中性化必须按 NEUTRALIZED_FIELDS 迭代，而不是硬编码字段名。
    否则往登记表里加字段不会生效，完整性测试却因它「已归类」而通过，
    造成有保护的错觉。
    """
    payload = {"case_no": "T1", **{f: "含 DR 3 级的内容" for f in NEUTRALIZED_FIELDS}}
    out = redact(payload, PresentationMode.TRAINING_BLINDED, case_no="T1")
    for field in NEUTRALIZED_FIELDS:
        assert "DR" not in str(out[field]), f"{field} 未被中性化"


# --------------------------------------------------------------------------
# 影像路径不得暴露病灶类型
# --------------------------------------------------------------------------

def test_blinded_strips_lesion_mask_paths_from_list():
    """
    掩码文件名形如 IDRiD_01_MA.png，文件名本身就说明该病例有微动脉瘤，
    等同于泄题。盲态下只保留原图。
    """
    payload = {
        "case_no": "T1",
        "images": [
            "/static/x/IDRiD_01.jpg",
            "/static/x/IDRiD_01_MA.png",
            "/static/x/IDRiD_01_HE.png",
            "/static/x/IDRiD_01_EX.png",
            "/static/x/IDRiD_01_overlay.png",
        ],
    }
    out = redact(payload, PresentationMode.TRAINING_BLINDED, case_no="T1")
    assert out["images"] == ["/static/x/IDRiD_01.jpg"]
    joined = " ".join(out["images"]).lower()
    for role in ("_ma", "_he", "_ex", "_se", "_overlay"):
        assert role not in joined


def test_blinded_strips_lesion_roles_from_grouped_paths():
    """按角色分组时整组病灶层丢弃，但眼别分组必须保留"""
    payload = {
        "case_no": "T1",
        "image_paths": {
            "OD": ["/static/a.jpg"],
            "OS": ["/static/b.jpg"],
            "MA": ["/static/a_MA.png"],
            "HE": ["/static/a_HE.png"],
        },
    }
    out = redact(payload, PresentationMode.TRAINING_BLINDED, case_no="T1")
    assert set(out["image_paths"]) == {"OD", "OS"}


def test_od_key_is_eye_not_lesion():
    """
    「OD」在本代码库中一词两义：image_paths 的键表示右眼，
    CaseImage.role 表示视盘掩码。按键名一刀切会把右眼影像误删。
    """
    payload = {"case_no": "T1", "image_paths": {"OD": ["/static/right_eye.jpg"]}}
    out = redact(payload, PresentationMode.TRAINING_BLINDED, case_no="T1")
    assert out["image_paths"].get("OD") == ["/static/right_eye.jpg"],         "右眼影像被当成视盘掩码删掉了"


@pytest.mark.parametrize("mode", [
    PresentationMode.TRAINING_REVIEW,
    PresentationMode.TEACHING_DEMO,
])
def test_non_blinded_keeps_all_paths(mode):
    """复盘与教学态需要看病灶层做对照，不能过滤"""
    payload = {"case_no": "T1",
               "images": ["/x/a.jpg", "/x/a_MA.png"]}
    out = redact(payload, mode, case_no="T1")
    assert len(out["images"]) == 2
