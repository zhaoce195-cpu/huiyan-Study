"""
盲训内容策略引擎（Content Presentation Policy）

解决《医学培训端评估与工作流重构报告》中的 P0 阻断项：
    学员在病例列表 / 练习入口 / 金标准接口处，于作答前即可拿到病名、DR 等级、
    金标准与病灶统计，导致训练与考核效度失真。

核心原则
    1. 答案裁剪发生在服务端，不依赖前端隐藏；
    2. 呈现模式由「场景 + 角色 + 作答状态」三元组在服务端推导，
       不接受前端或 URL 参数指定，避免被伪造；
    3. 答案型字段集中登记；新增字段必须显式归类，
       未归类字段会被 tests/test_content_policy.py 判为失败（默认按答案处理）。

四种呈现模式
    TRAINING_BLINDED  盲训：作答前，屏蔽一切答案型字段
    TRAINING_REVIEW   复盘：已提交，解锁答案用于对照学习
    TEACHING_DEMO     教学演示：教师主动讲解，答案可见
    CLINICAL          临床：真实阅片场景，按临床权限呈现
"""

from enum import Enum
from typing import Any, Dict, Iterable, Optional, Set


class PresentationMode(str, Enum):
    TRAINING_BLINDED = "TRAINING_BLINDED"
    TRAINING_REVIEW = "TRAINING_REVIEW"
    TEACHING_DEMO = "TEACHING_DEMO"
    CLINICAL = "CLINICAL"


class Scene(str, Enum):
    """调用场景（由路由显式声明，不从请求参数读取）"""
    CASE_BROWSE = "CASE_BROWSE"
    PRACTICE = "PRACTICE"
    READING = "READING"
    TEACHING = "TEACHING"


# ---------------------------------------------------------------------------
# 答案型字段登记表
# ---------------------------------------------------------------------------
# 键为 Pydantic 模型的 snake_case 字段名；值为盲态下的替代值。
# 只要字段出现在此表中，盲态就一定会被覆盖，不论它来自哪个模型。
ANSWER_FIELD_BLANKS: Dict[str, Any] = {
    # —— DR 分级类 ——
    "dr_level": None,
    "dr_grade": None,
    "dr_grade_text": "",
    "gold_dr_grade": None,
    # —— 金标准与教学答案 ——
    "gold_diagnosis": "",
    "gold_lesions": [],
    "teaching_points": "",
    "annotations": [],
    "lesions": [],
    "lesion_stats": None,
    # —— 结论型文本 ——
    "diagnosis": "",
    "diagnosis_text": "",
    # —— AI 结论（作答前等同于答案）——
    "ai_result": None,
    "ai_grade": None,
    "heatmap_url": "",
}

ANSWER_FIELDS: Set[str] = set(ANSWER_FIELD_BLANKS.keys())

# 需要「中性化」而非清空的字段：病例标题常含「DR 3 级」等答案信息，
# 直接清空会让列表不可用，因此替换为不含答案的可读标识。
NEUTRALIZED_FIELDS: Set[str] = {"title", "description"}

# 影像路径类字段：盲态下需过滤掉病灶层，只保留原图。
# 掩码文件名形如 IDRiD_01_MA.png / _HE / _EX / _SE，
# 文件名本身就暴露了该病例存在哪几类病灶——等同于泄题。
PATH_FIELDS: Set[str] = {"images", "image_paths"}

# 病灶层文件名的角色后缀（大小写不敏感）
_LESION_ROLE_SUFFIXES = ("_ma", "_he", "_ex", "_se", "_od",
                         "_mask", "_overlay", "_gold")

# 仅当键名明确只可能是病灶层时才整组丢弃。
# 刻意不含 "OD"：它在 image_paths 里是「右眼」，在 CaseImage.role 里才是「视盘」，
# 同名不同义，按键名一刀切会误删右眼影像。
_LESION_ONLY_KEYS = frozenset({
    "MA", "HE", "EX", "SE", "COLOR_MASK", "OVERLAY", "CLASS_MASK", "GOLD",
})


# 明确判定为「非答案」的安全字段。
# 与 ANSWER_FIELDS / NEUTRALIZED_FIELDS 共同构成完整分类，
# 新增字段若三者都不属于，完整性测试会失败。
SAFE_FIELDS: Set[str] = {
    # 标识与导航
    "id", "case_id", "case_no", "case_sn",
    # 学习目标类（报告允许在盲态展示：目标、难度、模态、是否计分）
    "category", "category_text", "difficulty", "difficulty_text",
    "pass_score", "estimated_minutes", "is_scored",
    # 影像与质量
    "image_count", "derived_count", "image_complete", "fundus_only",
    "missing_roles", "thumb_url", "modality", "laterality", "image_quality",
    # 病例状态
    "archive_status", "is_published", "is_train_case",
    # 临床输入信息（阅片的合法输入，非答案）
    "clinical_info",
    # 创建者与时间
    "creator_id", "creator_name", "creator_role", "created_at", "updated_at",
    # 患者信息（另有脱敏策略，见 case_utils.mask_phone_by_role）
    "patient_name", "patient_gender", "patient_age",
    "patient_phone", "phone_visible",
    "subject_no", "exam_on", "visit_count", "visit_index", "visits",
}


# ---------------------------------------------------------------------------
# 模式推导
# ---------------------------------------------------------------------------

_TEACHER_ROLES = {"TEACHER", "ADMIN"}


def resolve_mode(
    *,
    viewer_role: Optional[str],
    scene: Scene,
    answered: bool = False,
) -> PresentationMode:
    """
    依据「场景 + 角色 + 作答状态」推导呈现模式。

    注意：answered 必须由服务端查询作答记录得出，不可由前端传入。
    """
    role = (viewer_role or "").upper()

    # 练习入口（开始练习 / 换一份）一律不给答案。
    # 以前交过卷只解锁提交后的评分报告，不能让下一轮抽到的卡片提前出现 DR 等级。
    # 教师自己做题时同样遮住；备课和病例库仍对教师开放。
    if scene == Scene.PRACTICE:
        return PresentationMode.TRAINING_BLINDED

    if role in _TEACHER_ROLES:
        # 教师与管理员需要看到答案才能备课、审核与点评
        return PresentationMode.TEACHING_DEMO

    if scene in (Scene.CASE_BROWSE, Scene.PRACTICE, Scene.READING):
        return (
            PresentationMode.TRAINING_REVIEW
            if answered
            else PresentationMode.TRAINING_BLINDED
        )

    return PresentationMode.TRAINING_BLINDED


def is_blinded(mode: PresentationMode) -> bool:
    return mode is PresentationMode.TRAINING_BLINDED


# ---------------------------------------------------------------------------
# 字段裁剪
# ---------------------------------------------------------------------------

def redact(
    data: Dict[str, Any],
    mode: PresentationMode,
    *,
    case_no: str = "",
    keep: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """
    按呈现模式裁剪一份已序列化的病例数据（snake_case 键）。

    :param data:    模型 model_dump() 的结果
    :param mode:    呈现模式
    :param case_no: 用于生成中性标题
    :param keep:    例外白名单，即便处于盲态也保留的字段（谨慎使用）
    :return:        裁剪后的新字典，不修改入参
    """
    if not is_blinded(mode):
        return dict(data)

    keep_set = set(keep or ())
    out = dict(data)

    for field, blank in ANSWER_FIELD_BLANKS.items():
        if field in out and field not in keep_set:
            # 列表 / 字典等可变默认值需要复制，避免共享引用
            out[field] = list(blank) if isinstance(blank, list) else blank

    # 按登记表迭代，而不是硬编码字段名——否则往 NEUTRALIZED_FIELDS
    # 里加字段不会生效，而完整性测试又因它「已归类」而通过，
    # 造成有保护的错觉。
    for field in NEUTRALIZED_FIELDS:
        if field not in out or field in keep_set:
            continue
        out[field] = _neutral_value(field, case_no)

    # 影像路径：滤掉病灶层，只留原图
    for field in PATH_FIELDS:
        if field not in out or field in keep_set:
            continue
        out[field] = _strip_lesion_paths(out[field])

    return out


def _is_lesion_path(path: str) -> bool:
    """文件名是否暴露病灶类型"""
    name = str(path).rsplit("/", 1)[-1].rsplit(".", 1)[0].lower()
    return any(name.endswith(sfx) for sfx in _LESION_ROLE_SUFFIXES)


def _strip_lesion_paths(value: Any) -> Any:
    """
    从影像路径集合中移除病灶层。

    同时支持列表（images）与按角色分组的字典（image_paths）。
    """
    if isinstance(value, list):
        return [p for p in value if not _is_lesion_path(p)]
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for key, paths in value.items():
            # 注意：不能按键名判断是否为病灶层。
            # 本代码库中 "OD" 同时表示「右眼」（image_paths 的键）
            # 与「视盘掩码」（CaseImage.role），按键名丢弃会把右眼影像一起删掉。
            # 因此统一只按文件名后缀过滤，键名一律保留。
            if str(key).upper() in _LESION_ONLY_KEYS:
                continue
            if isinstance(paths, list):
                kept = [p for p in paths if not _is_lesion_path(p)]
                if kept:
                    out[key] = kept
            else:
                out[key] = paths
        return out
    return value


def _neutral_value(field: str, case_no: str) -> str:
    """中性化取值：标题保留可读标识，其余文本清空"""
    if field == "title":
        return f"病例 {case_no}" if case_no else "待判读病例"
    return ""


def assert_no_answer_leak(data: Dict[str, Any]) -> None:
    """
    自检辅助：断言一份盲态数据里不含任何未清空的答案字段。
    供测试与调试使用，生产路径不调用。
    """
    leaked = []
    for field, blank in ANSWER_FIELD_BLANKS.items():
        if field not in data:
            continue
        value = data[field]
        if value != blank and value not in (None, "", [], {}, 0):
            leaked.append(f"{field}={value!r}")
    if leaked:
        raise AssertionError("盲态响应泄露答案字段：" + ", ".join(leaked))
