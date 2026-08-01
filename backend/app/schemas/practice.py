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
    viewport: Optional[Dict[str, Any]] = None
    duration_seconds: int = 0


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
    student_annotations: List[Dict[str, Any]] = Field(default_factory=list)
    student_measurements: List[Dict[str, Any]] = Field(default_factory=list)
    viewport: Optional[Dict[str, Any]] = None

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
    error_points: List[Dict[str, Any]] = Field(default_factory=list)
    suggestion: str = ""

    started_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    duration_seconds: int = 0

    teacher_comment: str = ""
    teacher_id: Optional[int] = None
    teacher_name: str = ""

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


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
    pass_rate: float = 0.0
    avg_score: float = 0.0
    avg_iou: float = 0.0
    total_duration: int = 0
    weak_labels: List[WeakLabelItem] = Field(default_factory=list)
    by_difficulty: List[Dict[str, Any]] = Field(default_factory=list)
