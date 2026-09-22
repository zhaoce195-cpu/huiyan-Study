"""
教学实训分享 Pydantic schema
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


# ====================== 入参 ======================

class TeachingShareCreate(_CamelModel):
    source_type: Literal["SCREENING", "TRAINING"]
    source_case_id: int
    share_scope: str = "ALL"
    expire_hours: int = Field(default=24, ge=1, le=720)


class TeachingSubmitCreate(_CamelModel):
    source_type: Literal["SCREENING", "TRAINING"]
    source_case_id: int
    title: str = ""
    description: str = ""


class TeachingReviewParams(_CamelModel):
    accept: bool
    comment: str = ""


# ====================== 出参 ======================

class TeachingShareOut(_CamelModel):
    id: int
    share_type: str
    source_type: str
    source_case_id: int
    teaching_case_id: Optional[int] = None
    desensitized_data: Dict[str, Any] = {}
    share_scope: str = "ALL"
    expire_hours: int = 24
    expired_at: Optional[datetime] = None
    status: str
    review_comment: str = ""
    reviewed_at: Optional[datetime] = None
    reviewer_name: str = ""
    teacher_id: int
    teacher_name: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TeachingSharePage(_CamelModel):
    total: int = 0
    page: int = 1
    page_size: int = 20
    list: List[TeachingShareOut] = []


class StudentCaseOut(_CamelModel):
    id: int
    share_type: str
    title: str = ""
    description: str = ""
    patient_age: Optional[int] = None
    patient_gender: str = "U"
    clinical_info: str = ""
    category: str = ""
    difficulty: str = ""
    image_paths: Optional[Dict[str, Any]] = None
    image_count: int = 0
    teacher_name: str = ""
    # 演示正文：开始练习前不给这些，演示页必须给，否则只是病例陈列
    teaching_points: str = ""
    gold_diagnosis: str = ""
    gold_grade_text: str = ""
    category_text: str = ""
    difficulty_text: str = ""
    lesions: List[Dict[str, Any]] = Field(default_factory=list)
    annotations: List[Dict[str, Any]] = Field(default_factory=list)
    lesion_mask_url: str = ""
    expired_at: Optional[datetime] = None
    teaching_case_id: Optional[int] = None


class StudentCasePage(_CamelModel):
    total: int = 0
    page: int = 1
    page_size: int = 20
    list: List[StudentCaseOut] = []
