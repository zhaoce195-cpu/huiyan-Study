"""
病患手机号注册 / 验证码 / 我的体检报告 schema
- 与 frontend/src/api/patient.ts 对齐
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel


# ====================== 验证码 ======================

class SendCodeParams(BaseModel):
    phone: str = Field(..., description="手机号")

    @field_validator("phone")
    @classmethod
    def _phone_fmt(cls, v: str) -> str:
        v = (v or "").strip()
        if not v.isdigit() or len(v) != 11 or not v.startswith("1"):
            raise ValueError("手机号格式不正确")
        return v


class SendCodeResult(BaseModel):
    phone: str
    code: str = Field(..., description="模拟环境直接返回；生产环境应只发短信")
    expires_in: int = Field(..., description="有效期（秒）")


# ====================== 注册 ======================

class RegisterParams(BaseModel):
    phone: str = Field(..., description="手机号")
    password: str = Field(..., min_length=6, max_length=64)
    code: str = Field(..., min_length=4, max_length=8, description="短信验证码")
    real_name: Optional[str] = Field(None, max_length=32)

    @field_validator("phone")
    @classmethod
    def _phone_fmt(cls, v: str) -> str:
        v = (v or "").strip()
        if not v.isdigit() or len(v) != 11 or not v.startswith("1"):
            raise ValueError("手机号格式不正确")
        return v


# ====================== 病患报告 ======================

class _CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        arbitrary_types_allowed=True,
    )


class PatientReportItem(_CamelModel):
    case_id: int
    case_no: str = ""
    patient_name: str = ""
    gender: str = ""
    age: Optional[int] = None
    chief_complaint: str = ""
    medical_history: str = ""

    images: List[str] = Field(default_factory=list)
    image_count: int = 0

    status: str = ""
    status_text: str = ""

    # AI / 医生结论（取最近一次结果）
    dr_grade: str = ""
    dr_grade_text: str = ""
    risk_level: str = ""
    risk_level_text: str = ""
    risk_score: float = 0.0
    referral_required: bool = False
    lesions: List[Dict[str, Any]] = Field(default_factory=list)
    doctor_diagnosis: str = ""
    doctor_grade: str = ""
    doctor_name: str = ""

    submit_at: Optional[datetime] = None
    review_at: Optional[datetime] = None
    inferred_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    # 报告确认 / PDF 推送
    report_status: str = Field("pending", description="pending / confirmed")
    report_pdf_url: str = Field("", description="病患可访问的 PDF 接口路径")
    pdf_available: bool = Field(False, description="是否可预览/下载 PDF")


class PatientReportPage(_CamelModel):
    total: int = 0
    page: int = 1
    page_size: int = 20
    list: List[PatientReportItem] = Field(default_factory=list)


class BindCaseParams(_CamelModel):
    case_id: int
    patient_phone: str

    @field_validator("patient_phone")
    @classmethod
    def _phone_fmt(cls, v: str) -> str:
        v = (v or "").strip()
        if v and (not v.isdigit() or len(v) != 11 or not v.startswith("1")):
            raise ValueError("手机号格式不正确")
        return v
