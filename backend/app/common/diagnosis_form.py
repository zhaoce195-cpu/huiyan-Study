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

import re
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
        "hint": "这里只判断视网膜病变的级别。黄斑水肿另填，不要用级别高低代替。",
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
]

# 一张普通眼底照上允许的黄斑水肿记录。不能写成中心受累。
_FUNDUS_DME_OPTIONS = [
    {"value": "not_from_photo", "label": "这张眼底照不能判断黄斑水肿"},
    {"value": "no_exudate_clue", "label": "黄斑区未见硬性渗出，仍不能排除黄斑水肿"},
    {
        "value": "suspect_needs_oct",
        "label": "黄斑附近有硬性渗出，可疑黄斑水肿；是否中心受累要看 OCT 和视力",
    },
]

# 同时有 OCT 和视力时，才单独判断中心受累，并且仍不并入 DR 分级。
_CENTER_DME_OPTIONS = [
    {"value": "none", "label": "无黄斑水肿"},
    {"value": "non_center", "label": "非中心受累黄斑水肿"},
    {"value": "center", "label": "中心受累黄斑水肿"},
]

_FUNDUS_DME_HINT = (
    "黄斑水肿和 DR 分级分开判断。轻度也可以有黄斑水肿，重度也可以没有。"
    "这例只有普通眼底照，不能诊断中心受累黄斑水肿。"
    "若要训练中心受累黄斑水肿，病例需要同时提供 OCT 和视力。"
)

_CENTER_DME_HINT = (
    "本例同时有 OCT 和视力，可以单独判断是否为中心受累黄斑水肿。"
    "这个结论不由 DR 分级决定。"
)

# 这些值是在下黄斑水肿的诊断，眼底彩照单独不够。
_DME_DIAGNOSIS_VALUES = {"none", "non_center", "center", "non_csme", "csme"}

_VA_RE = re.compile(
    r"(?:最佳矫正视力|矫正视力|裸眼视力|BCVA|VA)\s*[:：]?\s*\d"
    r"|视力\s*[:：]\s*\d"
    r"|视力\s+\d"
)

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


def _text_has_visual_acuity(text: str) -> bool:
    """「视力下降」只是症状。要有具体数值才算提供了视力。"""
    return bool(_VA_RE.search(text or ""))


def _text_has_oct(text: str) -> bool:
    """结构 OCT 才算。OCTA 是血流成像，不能代替。"""
    stripped = re.sub(r"(?i)OCTA", " ", text or "")
    return bool(re.search(r"(?i)(?<![A-Za-z])OCT(?![A-Za-z])", stripped))


def _case_has_oct(case: Any, images: Optional[List[Any]] = None) -> bool:
    parts: List[str] = [getattr(case, "clinical_info", "") or ""]
    paths = getattr(case, "image_paths", None)
    if isinstance(paths, dict):
        for key, values in paths.items():
            parts.append(str(key))
            if isinstance(values, list):
                parts.extend(str(item) for item in values)
            elif values:
                parts.append(str(values))
    for image in images or []:
        parts.append(str(getattr(image, "file_name", "") or ""))
        parts.append(str(getattr(image, "file_url", "") or ""))
        parts.append(str(getattr(image, "role", "") or ""))
    return _text_has_oct("\n".join(parts))


def fundus_only(case: Any) -> bool:
    """教学病例默认只有眼底照相。有结构 OCT 或具体视力数值时才算另有资料。"""
    return not _case_has_oct(case) and not _text_has_visual_acuity(
        getattr(case, "clinical_info", "") or ""
    )


def materials_for_case(db: Any, case: Any) -> Dict[str, bool]:
    """中心受累黄斑水肿要同时有 OCT 和视力。教学要点里提到 OCT 不算提供了 OCT。"""
    images: List[Any] = []
    case_id = getattr(case, "id", None)
    if db is not None and case_id:
        from app.db.models import CaseImage, CaseImageTableEnum

        images = (
            db.query(CaseImage)
            .filter(
                CaseImage.case_table == CaseImageTableEnum.TRAINING.value,
                CaseImage.case_id == case_id,
            )
            .all()
        )
    return {
        "has_oct": _case_has_oct(case, images),
        "has_visual_acuity": _text_has_visual_acuity(getattr(case, "clinical_info", "") or ""),
    }


def center_dme_ready(materials: Optional[Dict[str, Any]]) -> bool:
    materials = materials or {}
    return bool(materials.get("has_oct") and materials.get("has_visual_acuity"))


def _dme_field(materials: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    ready = center_dme_ready(materials)
    return {
        "key": "dme",
        "label": "黄斑水肿（与 DR 分级分开）",
        "type": "radio",
        "required": False,
        "order": 45,
        "hint": _CENTER_DME_HINT if ready else _FUNDUS_DME_HINT,
        "options": list(_CENTER_DME_OPTIONS if ready else _FUNDUS_DME_OPTIONS),
    }


def get_form(
    category: Optional[str],
    materials: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    取某病种的表单定义。

    未登记的病种回退到通用结论字段，而不是套用 DR 量表——
    报告 5.1 明确要求表单必须病种特异。
    """
    cat = (category or "").strip().upper()
    specific = list(_CATEGORY_FIELDS.get(cat, _GENERIC_FIELDS))
    if cat == "DR":
        specific.append(_dme_field(materials))

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


# DR 分级 → 推荐处置（ICDR 通行随访间隔）
_DR_DISPOSITION = {
    "0": "followup_12m",
    "1": "followup_12m",
    "2": "followup_6m",
    "3": "followup_3m",
    "4": "refer_urgent",
}

# 金标准病灶标签 → 表单征象编码
_LESION_TO_FINDING = {
    "微动脉瘤": "MA",
    "出血": "HE",
    "视网膜出血": "HE",
    "硬性渗出": "EX",
    "渗出": "EX",
    "软性渗出": "SE",
    "棉绒斑": "SE",
    "新生血管": "NV",
}


def _normalize_finding(value: str) -> str:
    """把金标准里的病灶标识归一化为表单征象编码"""
    raw = str(value or "").strip()
    if not raw:
        return ""
    upper = raw.upper()
    if upper in ("MA", "HE", "EX", "SE", "NV", "IRMA", "VB"):
        return upper
    return _LESION_TO_FINDING.get(raw, "")


def gold_from_case(case: Any) -> Dict[str, Any]:
    """
    由病例已有字段推导结构化金标准。

    不要求教师重新录入一遍：分级、病灶标签都已存在，
    处置只按 DR 分级的通行随访间隔映射，不从级别推断黄斑水肿。
    这样存量病例无需人工补录就能参与结构化评分。

    金标准分级为空（不适用）时不给出 dr_grade，
    避免又把「不适用」变回某个具体分级。
    """
    category = (getattr(case, "category", "") or "").upper()
    grade = (getattr(case, "gold_dr_grade", "") or "").strip()

    gold: Dict[str, Any] = {"readability": "readable"}

    if category == "DR":
        if grade:
            gold["dr_grade"] = grade
            gold["disposition"] = _DR_DISPOSITION.get(grade, "routine")
        findings: List[str] = []
        has_lesion_data = False

        def _collect(raw: Any) -> None:
            nonlocal has_lesion_data
            for item in (raw or []):
                has_lesion_data = True
                if isinstance(item, dict):
                    # 金标准里病灶键名不统一：导入的数据用 type，
                    # 教师手工标注用 label，两种都要认
                    value = item.get("type") or item.get("label") or ""
                    # pixel_count 为 0 表示该类病灶实际不存在
                    if "pixel_count" in item and not item.get("pixel_count"):
                        continue
                else:
                    value = str(item)
                code = _normalize_finding(value)
                if code and code not in findings:
                    findings.append(code)

        _collect(getattr(case, "gold_lesions", None))
        _collect(getattr(case, "gold_annotations", None))

        # 只有确实存在病灶数据时才纳入评分。
        # 金标准没记录征象 ≠ 该病例没有征象——把「未知」当成「无」，
        # 会把学员的正确作答判成「多报」。
        if has_lesion_data:
            gold["findings"] = findings
        # 硬性渗出和 DR 级别都不能推出黄斑水肿。没有单独记录就不参与评分。

    return gold


def score_structured(
    category: Optional[str],
    student: Dict[str, Any],
    gold: Dict[str, Any],
) -> Dict[str, Any]:
    """
    结构化结论评分（0~100）。

    比关键词匹配可靠得多：关键词只能看学员有没有写到某几个词，
    写法稍有不同就判错，也无法区分「征象对但处置错」。

    :return: {"score": 分数, "detail": {各子项}, "errors": [错因]}
    """
    student = student or {}
    gold = gold or {}
    errors: List[str] = []
    parts: List[float] = []
    detail: Dict[str, Any] = {}

    # 征象：交并比，兼顾漏报与误报
    if "findings" in gold:
        s = set(student.get("findings") or [])
        g = set(gold.get("findings") or [])
        if g or s:
            inter = len(s & g)
            union = len(s | g) or 1
            f_score = inter / union * 100
            parts.append(f_score)
            detail["findings"] = round(f_score, 2)
            for miss in sorted(g - s):
                errors.append(f"漏报征象：{miss}")
            for extra in sorted(s - g):
                errors.append(f"多报征象：{extra}")

    # 黄斑水肿单独计分，不并进 DR 分级或征象。
    if gold.get("dme"):
        ok = student.get("dme") == gold.get("dme")
        parts.append(100.0 if ok else 0.0)
        detail["dme"] = 100.0 if ok else 0.0
        if not ok:
            errors.append("黄斑水肿要单独判断，不能用 DR 分级代替。")

    # 处置：对错二值——处置直接关系患者去向，没有部分正确
    if gold.get("disposition"):
        ok = student.get("disposition") == gold.get("disposition")
        parts.append(100.0 if ok else 0.0)
        detail["disposition"] = 100.0 if ok else 0.0
        if not ok:
            errors.append(
                f"处置建议不当：应为 {gold.get('disposition')}，"
                f"实际 {student.get('disposition') or '未填'}"
            )

    score = round(sum(parts) / len(parts), 2) if parts else 0.0
    return {"score": score, "detail": detail, "errors": errors}


def dme_answer_problem(
    answers: Optional[Dict[str, Any]],
    materials: Optional[Dict[str, Any]] = None,
) -> str:
    """眼底照上的黄斑水肿记录不能写成中心受累。空着则不拦。"""
    value = str((answers or {}).get("dme") or "").strip()
    if not value:
        return ""
    if center_dme_ready(materials):
        allowed = {item["value"] for item in _CENTER_DME_OPTIONS}
        if value not in allowed:
            return "黄斑水肿要单独选择：无、非中心受累，或中心受累。不要用 DR 分级代替。"
        return ""
    if value in _DME_DIAGNOSIS_VALUES:
        return (
            "这例没有同时提供 OCT 和视力，不能诊断中心受累黄斑水肿。"
            "黄斑水肿与 DR 分级分开判断。"
        )
    allowed = {item["value"] for item in _FUNDUS_DME_OPTIONS}
    if value not in allowed:
        return "黄斑水肿不能按 DR 分级来填。这张眼底照只能记录能否判断，或是否需要 OCT 和视力。"
    return ""


def validate(
    category: Optional[str],
    answers: Dict[str, Any],
    materials: Optional[Dict[str, Any]] = None,
) -> List[str]:
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

    dme_problem = dme_answer_problem(answers, materials)
    if dme_problem:
        problems.append(dme_problem)

    return problems
