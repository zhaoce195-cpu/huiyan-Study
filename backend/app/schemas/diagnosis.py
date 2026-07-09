"""
CSU-EYES 诊断 Schema
====================
- DiagnosisType（三选一）
- 三种结果体（MA / DR / 综合）
- DiagnosisOut 统一返回
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class _CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        arbitrary_types_allowed=True,
    )


class DiagnosisType(str, Enum):
    MA = "MA"
    DR = "DR"
    COMPREHENSIVE = "COMPREHENSIVE"


# ============ MA 结果 ============

class MaDiagnosisResult(_CamelModel):
    ma_count: int = 0
    overlay_url: str = ""
    heatmap_url: str = ""
    inference_time: float = 0.0


# ============ DR 结果 ============

class DrEyeResult(_CamelModel):
    grade: int = 0
    grade_name: str = ""
    image_url: str = ""
    heatmap_url: str = ""


class DrDiagnosisResult(_CamelModel):
    overall_grade: int = 0
    overall_grade_name: str = ""
    left: DrEyeResult = Field(default_factory=DrEyeResult)
    right: DrEyeResult = Field(default_factory=DrEyeResult)
    inference_time: float = 0.0


# ============ 综合诊断 ============

class ComprehensiveDiagnosisResult(_CamelModel):
    overall_grade: int = 0
    ma_count: int = 0
    ma_overlay_url: str = ""
    dr_heatmap_url: str = ""
    summary: str = ""
    inference_time: float = 0.0


# ============ 统一返回 ============

RiskLiteral = Literal["LOW", "MEDIUM", "HIGH", "URGENT"]


class DiagnosisOut(_CamelModel):
    task_id: str = Field(..., description="对应 ScreeningCase.case_no")
    case_id: int
    case_sn: str = ""
    patient_name: str = ""
    diagnosis_type: DiagnosisType
    risk_level: RiskLiteral = "LOW"
    primary_image_url: str = ""
    ma: Optional[MaDiagnosisResult] = None
    dr: Optional[DrDiagnosisResult] = None
    comprehensive: Optional[ComprehensiveDiagnosisResult] = None
    raw: Dict[str, Any] = Field(default_factory=dict, description="上游原始响应")


__all__ = [
    "DiagnosisType",
    "MaDiagnosisResult",
    "DrEyeResult",
    "DrDiagnosisResult",
    "ComprehensiveDiagnosisResult",
    "DiagnosisOut",
]
