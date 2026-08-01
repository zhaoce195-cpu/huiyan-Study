# -*- coding: utf-8 -*-
"""
结构化诊断表单定义

对应《医学培训端评估与工作流重构报告》P1：
    「阅片提交只有自由备注，缺少可判读性、征象、分级、置信度、处置和最终确认」
    「结论难评分、难审计、难统计」

设计要点
    1. 字段顺序遵循报告建议：质量 → 主要结论 → 关键征象 → 分级 → 置信度 → 处置，
       渐进展开而非一次铺开全部字段；
    2. 表单由配置定义、按病种加载，新增病种只加配置不改代码
       （报告 5.1：不要用单一 DR 量表覆盖青光眼、AMD 等病种）；
    3. 「不可判读」是一等结论：选中后不再要求填写分级与征象，
       且不得输出阴性结论（报告 P0「先质量后诊断」）。
"""

from typing import Any, Dict, List, Optional

# 影像可判读性——所有病种共用，永远排在最前
QUALITY_FIELD: Dict[str, Any] = {
    "key": "readability",
    "label": "影像可判读性",
    "type": "radio",
    "required": True,
    "order": 1,
    "options": [
        {"value": "readable", "label": "可判读"},
        {"value": "partially", "label": "部分可判读"},
        {"value": "ungradable", "label": "不可判读"},
    ],
    "hint": "先判断可判读性再下结论；不可判读时应重拍或转诊，不得给出阴性结论",
}

# 选中不可判读后，后续诊断字段整体跳过
UNGRADABLE_VALUE = "ungradable"

CONFIDENCE_FIELD: Dict[str, Any] = {
    "key": "confidence",
    "label": "结论置信度",
    "type": "radio",
    "required": True,
    "order": 90,
    "options": [
        {"value": "high", "label": "高"},
        {"value": "medium", "label": "中"},
        {"value": "low", "label": "低"},
    ],
    "hint": "置信度低的结论应进入教师复核队列",
}

DISPOSITION_FIELD: Dict[str, Any] = {
    "key": "disposition",
    "label": "处置建议",
    "type": "select",
    "required": True,
    "order": 95,
    "options": [
        {"value": "routine", "label": "常规随访"},
        {"value": "followup_3m", "label": "3 个月内复查"},
        {"value": "followup_6m", "label": "6 个月内复查"},
        {"value": "followup_12m", "label": "12 个月复查"},
        {"value": "refer", "label": "转诊眼科"},
        {"value": "refer_urgent", "label": "紧急转诊"},
        {"value": "retake", "label": "重新拍摄"},
    ],
}

NOTE_FIELD: Dict[str, Any] = {
    "key": "note",
    "label": "补充说明",
    "type": "textarea",
    "required": False,
    "order": 99,
    "placeholder": "结构化字段之外需要补充的内容",
    "hint": "自由文本仅作补充，不替代上面的结构化结论",
}

# 病种特异字段
_DR_FIELDS: List[Dict[str, Any]] = [
    {
        "key": "dr_grade",
        "label": "DR 分级",
        "type": "select",
        "required": True,
        "order": 20,
        "options": [
            {"value": "0", "label": "0 级 无 DR"},
            {"value": "1", "label": "1 级 轻度 NPDR"},
            {"value": "2", "label": "2 级 中度 NPDR"},
            {"value": "3", "label": "3 级 重度 NPDR"},
            {"value": "4", "label": "4 级 PDR（增殖性）"},
            {"value": "NA", "label": "不适用"},
        ],
    },
    {
        "key": "findings",
        "label": "关键征象",
        "type": "checkbox",
        "required": False,
        "order": 30,
        "options": [
            {"value": "MA", "label": "微动脉瘤"},
            {"value": "HE", "label": "视网膜出血"},
            {"value": "EX", "label": "硬性渗出"},
            {"value": "SE", "label": "软性渗出（棉绒斑）"},
            {"value": "IRMA", "label": "视网膜内微血管异常"},
            {"value": "VB", "label": "静脉串珠样改变"},
            {"value": "NV", "label": "新生血管"},
        ],
    },
    {
        "key": "dme",
        "label": "黄斑水肿",
        "type": "radio",
        "required": False,
        "order": 40,
        "options": [
            {"value": "none", "label": "无"},
            {"value": "non_csme", "label": "有，非临床显著"},
            {"value": "csme", "label": "临床显著性黄斑水肿"},
        ],
    },
]

_GLAUCOMA_FIELDS: List[Dict[str, Any]] = [
    {
        "key": "cdr",
        "label": "杯盘比（C/D）",
        "type": "select",
        "required": True,
        "order": 20,
        "options": [{"value": v, "label": v} for v in
                    ["<0.4", "0.4-0.5", "0.5-0.6", "0.6-0.7", "0.7-0.8", ">0.8"]],
    },
    {
        "key": "glaucoma_findings",
        "label": "关键征象",
        "type": "checkbox",
        "required": False,
        "order": 30,
        "options": [
            {"value": "rim_notch", "label": "盘沿切迹"},
            {"value": "rnfl_defect", "label": "视网膜神经纤维层缺损"},
            {"value": "disc_hemorrhage", "label": "视盘出血"},
            {"value": "peripapillary_atrophy", "label": "视盘周围萎缩"},
        ],
    },
    {
        "key": "glaucoma_risk",
        "label": "青光眼风险",
        "type": "radio",
        "required": True,
        "order": 40,
        "options": [
            {"value": "low", "label": "低"},
            {"value": "suspect", "label": "可疑"},
            {"value": "high", "label": "高"},
        ],
        "hint": "眼底照仅能提示风险，确诊需结合眼压、视野与 OCT",
    },
]

_AMD_FIELDS: List[Dict[str, Any]] = [
    {
        "key": "amd_type",
        "label": "AMD 类型",
        "type": "radio",
        "required": True,
        "order": 20,
        "options": [
            {"value": "none", "label": "无"},
            {"value": "dry", "label": "干性（萎缩型）"},
            {"value": "wet", "label": "湿性（渗出型）"},
        ],
    },
    {
        "key": "amd_findings",
        "label": "关键征象",
        "type": "checkbox",
        "required": False,
        "order": 30,
        "options": [
            {"value": "drusen", "label": "玻璃膜疣"},
            {"value": "pigment", "label": "色素紊乱"},
            {"value": "ga", "label": "地图状萎缩"},
            {"value": "cnv", "label": "脉络膜新生血管"},
        ],
    },
]

_CATEGORY_FIELDS: Dict[str, List[Dict[str, Any]]] = {
    "DR": _DR_FIELDS,
    "GLAUCOMA": _GLAUCOMA_FIELDS,
    "AMD": _AMD_FIELDS,
}

# 无病种特异表单时的通用结论
_GENERIC_FIELDS: List[Dict[str, Any]] = [
    {
        "key": "impression",
        "label": "主要结论",
        "type": "text",
        "required": True,
        "order": 20,
        "placeholder": "用一句话概括主要发现",
    },
]


def get_form(category: Optional[str]) -> Dict[str, Any]:
    """
    取某病种的表单定义。

    未登记的病种回退到通用结论字段，而不是套用 DR 量表——
    报告 5.1 明确要求表单必须病种特异。
    """
    cat = (category or "").strip().upper()
    specific = _CATEGORY_FIELDS.get(cat, _GENERIC_FIELDS)

    fields = [QUALITY_FIELD, *specific, CONFIDENCE_FIELD,
              DISPOSITION_FIELD, NOTE_FIELD]
    fields = sorted(fields, key=lambda f: f["order"])

    return {
        "category": cat or "OTHER",
        "categoryKnown": cat in _CATEGORY_FIELDS,
        "ungradableValue": UNGRADABLE_VALUE,
        # 选中不可判读后需要跳过的字段
        "skipWhenUngradable": [
            f["key"] for f in fields
            if f["key"] not in ("readability", "disposition", "note")
        ],
        "fields": fields,
    }


def required_keys(category: Optional[str], readability: str = "") -> List[str]:
    """
    该病种下的必填字段。

    不可判读时只要求处置建议——此时再逼学员填分级与征象没有意义，
    还会诱导他对着不可判读的图硬猜。
    """
    form = get_form(category)
    if readability == UNGRADABLE_VALUE:
        return [f["key"] for f in form["fields"]
                if f["required"] and f["key"] in ("readability", "disposition")]
    return [f["key"] for f in form["fields"] if f["required"]]


def validate(category: Optional[str], answers: Dict[str, Any]) -> List[str]:
    """
    校验结构化结论，返回缺失项的中文提示；无问题返回空列表。
    """
    answers = answers or {}
    readability = str(answers.get("readability") or "")
    form = get_form(category)
    label_of = {f["key"]: f["label"] for f in form["fields"]}

    problems: List[str] = []
    for key in required_keys(category, readability):
        value = answers.get(key)
        if value is None or value == "" or value == []:
            problems.append(f"请填写「{label_of.get(key, key)}」")

    # 不可判读却给出阴性结论：这正是报告 P0 要防的
    if readability == UNGRADABLE_VALUE:
        if str(answers.get("dr_grade") or "") == "0":
            problems.append("影像不可判读时不能给出「0 级 无 DR」的阴性结论")
        if str(answers.get("disposition") or "") in ("routine",):
            problems.append("影像不可判读时不应只做常规随访，请选择重新拍摄或转诊")

    return problems
