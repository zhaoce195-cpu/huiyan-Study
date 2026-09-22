"""
AI 筛查模块 Pydantic schema
- 与前端 frontend/src/api/screening.ts 字段一一对应
- 通过 alias_generator=to_camel 将 snake_case ↔ camelCase
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


# ====================== 公共 ======================

class _CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        arbitrary_types_allowed=True,
    )


RiskLiteral = Literal["red", "yellow", "green"]
ScreeningStatusLiteral = Literal["queued", "analyzing", "done", "failed"]
EyeSideLiteral = Literal["OD", "OS", "OU", "UK"]
GenderLiteral = Literal["男", "女"]
SortByLiteral = Literal["risk", "createdAt", "confidence"]
SortOrderLiteral = Literal["asc", "desc"]


# ====================== 上传相关 ======================

class PatientMetaForm(_CamelModel):
    """眼底图上传时附带的患者元信息（multipart 表单字段）"""
    patient_id: Optional[str] = None
    patient_name: Optional[str] = None
    gender: Optional[GenderLiteral] = None
    age: Optional[int] = Field(None, ge=0, le=150)
    eye: Optional[EyeSideLiteral] = None
    hospital: Optional[str] = None
    doctor: Optional[str] = None
    remark: Optional[str] = None
    patient_phone: Optional[str] = Field(
        None, description="病患账号手机号（用于绑定到病患账号）",
    )


class UploadFundusResult(_CamelModel):
    task_id: str
    file_url: str
    file_name: str
    file_size: int
    queued: bool = True


class BatchUploadResult(_CamelModel):
    total: int
    success: int
    failed: int
    items: List[UploadFundusResult] = Field(default_factory=list)


# ====================== 任务列表 ======================

class ScreeningTaskOut(_CamelModel):
    id: str
    # 数据库主键（用于 patient/bind_case 等需要数字 ID 的接口）
    case_id: int = 0
    patient_id: str = ""
    patient_name: str = ""
    patient_phone: str = ""
    eye: EyeSideLiteral = "OU"
    age: int = 0
    gender: GenderLiteral = "男"
    status: ScreeningStatusLiteral = "queued"
    risk: Optional[RiskLiteral] = None
    dr: str = ""
    confidence: float = 0.0
    created_at: str = ""
    file_name: str = ""
    file_url: Optional[str] = None
    thumb_url: Optional[str] = None
    hospital: str = ""
    doctor: str = ""
    remark: str = ""
    # 是否已绑定到 patient 用户账号（通过 patient_phone 匹配 sys_user.phone）
    patient_bound: bool = False
    # 是否已医生确认（status=REVIEWED）
    confirmed: bool = False
    reviewer: Optional[str] = None
    reviewed_at: Optional[str] = None
    # ============ CSU-EYES 智能诊断 ============
    diagnosis_type: Optional[str] = Field(
        None, description="MA / DR / COMPREHENSIVE，未做诊断时为 None"
    )
    diagnosis_summary: str = Field(
        "", description="一句话诊断摘要：如 'DR 3级 重度' / 'MA 12 个'"
    )
    heatmap_url: Optional[str] = Field(
        None, description="任一只眼的热力图/标注图 URL（用于列表预览）"
    )


class ScreeningPageResult(_CamelModel):
    total: int
    page: int
    page_size: int
    list: List[ScreeningTaskOut]


# ====================== 重新分析 ======================

class ReanalyzeParams(_CamelModel):
    task_id: str
    force: bool = False


# ====================== 统计 ======================

class ScreeningStatsOut(_CamelModel):
    total: int = 0
    red: int = 0
    yellow: int = 0
    green: int = 0
    pending: int = 0
    failed: int = 0
    today_count: int = 0
    week_count: int = 0


# ====================== 报告 ======================

class LesionItem(_CamelModel):
    type: str
    count: int = 0
    location: Optional[str] = None


class ImageUrls(_CamelModel):
    origin: str = ""
    heatmap: Optional[str] = None


class ScreeningReportOut(_CamelModel):
    task_id: str
    patient_id: str = ""
    patient_name: str = ""
    gender: GenderLiteral = "男"
    age: int = 0
    eye: EyeSideLiteral = "OU"
    hospital: str = ""
    doctor: str = ""
    exam_time: str = ""
    report_time: str = ""
    report_no: str = ""
    risk: RiskLiteral = "green"
    dr: str = ""
    confidence: float = 0.0
    conclusion: str = ""
    suggestion: str = ""
    lesions: List[LesionItem] = Field(default_factory=list)
    image_urls: ImageUrls = Field(default_factory=ImageUrls)
    reviewer: Optional[str] = None
    reviewed_at: Optional[str] = None


# ====================== 转诊 ======================

class ReferParams(_CamelModel):
    task_id: str
    target_hospital: str = Field(..., min_length=2, max_length=128)
    note: Optional[str] = None


# ====================== 报告确认 ======================

class ConfirmReportParams(_CamelModel):
    task_id: str
    diagnosis: Optional[str] = Field(None, description="医生确认的诊断意见，留空使用 AI 结论")
    suggestion: Optional[str] = Field(None, description="医生确认的建议处置")


class ConfirmReportResult(_CamelModel):
    task_id: str
    case_id: int
    status: ScreeningStatusLiteral = "done"
    reviewer: str = ""
    reviewed_at: str = ""
    patient_bound: bool = False
    patient_phone: str = ""
    # 病患账号（命中时返回，方便前端展示）
    patient_user_id: Optional[int] = None
    # 报告确认状态
    report_status: Literal["pending", "confirmed"] = "confirmed"
    # PDF 静态访问 URL（病患可用 /patient/report-pdf/{caseId} 拿，前端可任选）
    report_pdf_url: str = ""


# ====================== 病例编辑（医生 / 管理员补充修改） ======================

class CaseUpdateParams(_CamelModel):
    """医生/管理员补充修改病例的可写字段。所有字段可选，按提供项部分更新。"""
    patient_name: Optional[str] = Field(None, max_length=64)
    gender: Optional[GenderLiteral] = None
    age: Optional[int] = Field(None, ge=0, le=150)
    patient_phone: Optional[str] = Field(
        None, description="联系电话（同时同步 phone 与 patient_phone）",
    )
    chief_complaint: Optional[str] = Field(None, max_length=255)
    medical_history: Optional[str] = Field(None, max_length=2000)
    remark: Optional[str] = Field(
        None, max_length=512,
        description="病例诊断结果 / 备注",
    )


class CaseImageItem(_CamelModel):
    eye: EyeSideLiteral = "OU"
    url: str
    file_name: str = ""


class CaseImagesResult(_CamelModel):
    case_id: int
    image_count: int
    images: List[CaseImageItem] = Field(default_factory=list)


class CaseImageDeleteParams(_CamelModel):
    url: str = Field(..., description="要删除的影像 URL（image_paths 中的相对路径）")


class BatchTaskIdsParams(_CamelModel):
    """批量操作入参：传入多个 taskId（即 case_no）"""
    task_ids: List[str] = Field(
        ..., min_length=1, max_length=500,
        description="要批量处理的 taskId 列表",
    )


class BatchTaskOpResult(_CamelModel):
    """批量操作出参"""
    success_count: int = Field(0, description="成功处理的条数")
    skipped_count: int = Field(0, description="未处理（不符合条件）的条数")
    failed_count: int = Field(0, description="处理失败条数")
    failed_ids: List[str] = Field(default_factory=list, description="失败的 taskId 列表")


__all__ = [
    "PatientMetaForm",
    "UploadFundusResult",
    "BatchUploadResult",
    "ScreeningTaskOut",
    "ScreeningPageResult",
    "ReanalyzeParams",
    "ScreeningStatsOut",
    "LesionItem",
    "ImageUrls",
    "ScreeningReportOut",
    "ReferParams",
    "ConfirmReportParams",
    "ConfirmReportResult",
    "CaseUpdateParams",
    "CaseImageItem",
    "CaseImagesResult",
    "CaseImageDeleteParams",
    "BatchTaskIdsParams",
    "BatchTaskOpResult",
]
