"""
自主练习模块 Pydantic schema
- 病例随机抽取/指定病例练习
- 金标准查询
- 练习提交（自动评分）
- 练习台账与详情
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class _CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        arbitrary_types_allowed=True,
    )


PracticeStatusLiteral = Literal["DRAFT", "SUBMITTED", "REVIEWED"]
PracticeModeLiteral = Literal["RANDOM", "SELECTED"]
ErrorTypeLiteral = Literal["missed", "false_positive", "low_iou", "wrong_label"]


# ====================== 公共 ======================

class Point2D(_CamelModel):
    x: float
    y: float


class PracticeAnnotation(_CamelModel):
    """学员/金标准标注通用结构"""
    id: str = ""
    tool: str = "rect"
    points: List[Point2D] = Field(default_factory=list)
    label: str = ""
    color: Optional[str] = None
    layer: str = "primary"
    remark: str = ""
    value: Optional[float] = None
    unit: Optional[str] = None


class GoldStandardData(_CamelModel):
    """金标准（专家标注）"""
    case_id: int
    case_no: str
    dr_grade: str = "0"
    dr_grade_text: str = ""
    diagnosis: str = ""
    teaching_points: str = ""
    annotations: List[PracticeAnnotation] = Field(default_factory=list)
    lesions: List[Dict[str, Any]] = Field(default_factory=list)
    # 彩色病灶图或叠加图。空字符串表示这例没有金标准图像，只有可能有标注框。
    lesion_mask_url: str = ""
    pass_score: int = 60


# ====================== 入参 ======================

class PracticeRandomQuery(_CamelModel):
    category: Optional[str] = Field(None, description="病种过滤")
    difficulty: Optional[str] = Field(None, description="难度过滤 EASY/MEDIUM/HARD")
    dr_level: Optional[int] = Field(None, ge=0, le=4)
    exclude_done: bool = Field(True, description="排除已完成的病例")


class PracticeStartParams(_CamelModel):
    case_id: int = Field(..., description="病例 PK 主键")
    mode: PracticeModeLiteral = "SELECTED"


class TextQuizAnswerIn(_CamelModel):
    id: str
    value: str = ""


class PracticeSubmitParams(_CamelModel):
    session_id: int
    student_dr_grade: str = Field(..., description="DR 分级 0~4")
    student_diagnosis: str = ""
    diagnosis: Dict[str, Any] = Field(
        default_factory=dict,
        description="结构化诊断作答；提供时按结构化口径评分",
    )
    annotations: List[PracticeAnnotation] = Field(default_factory=list)
    measurements: List[PracticeAnnotation] = Field(default_factory=list)
    text_answers: List[TextQuizAnswerIn] = Field(default_factory=list)
    viewport: Optional[Dict[str, Any]] = None
    duration_seconds: int = 0
    request_id: str = Field(
        "",
        max_length=64,
        description="提交幂等键：断网重试时原样带回，同键返回原结果而非报错",
    )


class PracticeReviewParams(_CamelModel):
    teacher_comment: str = Field("", description="教师点评")


class PracticeListQuery(_CamelModel):
    user_id: Optional[int] = None
    case_id: Optional[int] = None
    status: Optional[PracticeStatusLiteral] = None
    is_passed: Optional[bool] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=200)


# ====================== 出参 ======================

class CaseBriefForPractice(_CamelModel):
    case_id: int
    case_no: str
    title: str = ""
    category: str = ""
    category_text: str = ""
    difficulty: str = ""
    difficulty_text: str = ""
    # 盲训态下为 None：作答前不得下发正确分级
    dr_level: Optional[int] = None
    dr_grade_text: str = ""
    images: List[str] = Field(default_factory=list)
    image_count: int = 0
    pass_score: int = 60


class ErrorPoint(_CamelModel):
    type: ErrorTypeLiteral
    label: str = ""
    expected_label: Optional[str] = None
    iou: Optional[float] = None
    point: Optional[Point2D] = None
    note: str = ""


class PracticeScoreDetail(_CamelModel):
    """评分细节（用于报告页展示）"""
    score_total: float = 0.0
    score_grade: float = 0.0
    score_annotation: float = 0.0
    score_diagnosis: float = 0.0
    iou_avg: float = 0.0
    accuracy: float = 0.0
    grade_match: bool = False
    is_passed: bool = False
    missed_count: int = 0
    false_positive_count: int = 0
    error_points: List[ErrorPoint] = Field(default_factory=list)
    suggestion: str = ""


class PracticeOut(_CamelModel):
    id: int
    user_id: int
    user_name: str = ""
    case_id: int
    case_no: str = ""
    case_title: str = ""
    case_category: str = ""
    case_difficulty: str = ""
    case_dr_grade_text: str = ""
    images: List[str] = Field(default_factory=list)
    mode: PracticeModeLiteral = "SELECTED"
    status: PracticeStatusLiteral = "DRAFT"

    student_dr_grade: str = ""
    student_diagnosis: str = ""
    # 结构化作答要回传：报告页得把学员填的每一项摊开对照，
    # 只给一个总分，学员看不出自己错在哪一条
    student_diagnosis_form: Dict[str, Any] = Field(default_factory=dict)
    # 这份成绩按哪套口径判的。存量记录是 keyword，新记录是 structured，
    # 分数不可直接横向比较，界面上要说清楚
    scoring_mode: str = "keyword"
    # 标注分算法版本。分数不可直接横向比较：
    # 1：没有金标准框时标注分最高 70，总分封顶 85。
    # 2：没有框时把「没标」记成 100。
    # 3：没有框且没标则标注未考，权重摊给其余项。
    # 4：文字题占 20%，分级 25%、标注 40%、诊断 15%。
    # 5：病例学习。分级 40%、诊断 40%、文字题 20%。标注不计入总分。
    score_rule_version: int = 1
    student_annotations: List[Dict[str, Any]] = Field(default_factory=list)
    student_measurements: List[Dict[str, Any]] = Field(default_factory=list)
    viewport: Optional[Dict[str, Any]] = None

    score_total: float = 0.0
    score_grade: float = 0.0
    score_annotation: float = 0.0
    # 假：这例没有金标准框，学员也没画。界面显示「未考」，不要把库存的 100 当成答对。
    annotation_applicable: bool = True
    score_diagnosis: float = 0.0
    score_text: float = 0.0
    # 作答前只有题面。交卷后 text_items 才带标准答案和讲解。
    text_questions: List[Dict[str, Any]] = Field(default_factory=list)
    text_items: List[Dict[str, Any]] = Field(default_factory=list)
    # PRACTICE 平时练习可逐则看提示；EXAM 正式考试整卷交齐后才开放答案。
    attempt_kind: str = "PRACTICE"
    exam_group_id: str = ""
    exam_index: int = 0
    exam_total: int = 0
    answers_open: bool = False
    hints: List[str] = Field(default_factory=list)
    hints_left: int = 0
    next_session_id: int = 0
    next_case_id: int = 0
    # 老师发布的正式考试。旧的自行开考没有这些字段。
    exam_paper_id: int = 0
    exam_title: str = ""
    allow_back: bool = False
    # -1 表示不限时。0 表示时间已到。
    exam_seconds_left: int = -1
    paper_closed: bool = False
    exam_pass_score: int = 0
    prev_session_id: int = 0
    prev_case_id: int = 0
    exam_items: List["ExamNavItem"] = Field(default_factory=list)
    iou_avg: float = 0.0
    accuracy: float = 0.0
    grade_match: bool = False
    is_passed: bool = False
    missed_count: int = 0
    false_positive_count: int = 0
    error_points: List[Dict[str, Any]] = Field(default_factory=list)
    suggestion: str = ""

    started_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    duration_seconds: int = 0

    teacher_comment: str = ""
    teacher_id: Optional[int] = None
    teacher_name: str = ""
    teacher_role: str = ""

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ExamNavItem(_CamelModel):
    index: int = 0
    session_id: int = 0
    case_id: int = 0
    status: str = ""


class PracticePage(_CamelModel):
    total: int = 0
    page: int = 1
    page_size: int = 20
    list: List[PracticeOut] = Field(default_factory=list)


# ====================== 统计 ======================

class WeakLabelItem(_CamelModel):
    label: str
    missed: int = 0
    false_positive: int = 0
    avg_iou: float = 0.0


class PracticeStats(_CamelModel):
    total_sessions: int = 0
    submitted_sessions: int = 0
    completed_cases: int = 0
    pass_rate: float = 0.0
    avg_score: float = 0.0
    avg_iou: float = 0.0
    total_duration: int = 0
    weak_labels: List[WeakLabelItem] = Field(default_factory=list)
    by_difficulty: List[Dict[str, Any]] = Field(default_factory=list)


# ====================== 文字题 ======================

class TextQuizQuestionOut(_CamelModel):
    id: str
    kind: Literal["knowledge", "choice", "blank"]
    kind_text: str
    stem: str
    options: List[str] = Field(default_factory=list)


class TextQuizPaperOut(_CamelModel):
    questions: List[TextQuizQuestionOut] = Field(default_factory=list)


class TextQuizSubmitIn(_CamelModel):
    answers: List[TextQuizAnswerIn] = Field(default_factory=list)


class TextQuizItemResult(_CamelModel):
    id: str
    kind: str
    kind_text: str
    stem: str
    yours: str = ""
    expected: str = ""
    correct: bool = False
    explanation: str = ""


class TextQuizResultOut(_CamelModel):
    score: int = 0
    correct_count: int = 0
    question_count: int = 0
    passed: bool = False
    items: List[TextQuizItemResult] = Field(default_factory=list)


PracticeOut.model_rebuild()
