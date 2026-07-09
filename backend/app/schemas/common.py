"""
公共模块 Pydantic schema
- 与前端 frontend/src/api/common.ts 字段一一对应
"""

from typing import List, Literal, Optional, Union

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


# ====================== 字典 ======================

class DictItemOut(_CamelModel):
    code: str
    label: str
    sort: Optional[int] = 0
    remark: Optional[str] = ""
    children: Optional[List["DictItemOut"]] = None


class DictBatchParams(_CamelModel):
    types: List[str] = Field(default_factory=list)


# ====================== 医院 / 科室 ======================

class HospitalOut(_CamelModel):
    id: Union[int, str]
    name: str
    level: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None


class DepartmentOut(_CamelModel):
    id: Union[int, str]
    name: str
    hospital_id: Optional[Union[int, str]] = None


class DepartmentSaveParams(_CamelModel):
    code: Optional[str] = Field(None, max_length=32)
    name: str = Field(..., min_length=1, max_length=64)
    short_name: Optional[str] = Field(None, max_length=32)
    leader: Optional[str] = Field(None, max_length=32)
    phone: Optional[str] = Field(None, max_length=32)
    sort_order: Optional[int] = 0
    is_active: Optional[bool] = True
    remark: Optional[str] = Field(None, max_length=255)


# ====================== 系统配置 ======================

class SystemConfigOut(_CamelModel):
    app_name: str
    version: str
    record_no: Optional[str] = None
    terms_url: Optional[str] = None
    privacy_url: Optional[str] = None
    upload_max_mb: int = 20
    accept_image_types: List[str] = Field(default_factory=list)


# ====================== 文件上传 ======================

class UploadFileResultOut(_CamelModel):
    url: str
    full_url: str
    file_name: str
    file_size: int
    mime_type: str


# ====================== 通知 ======================

class NotificationItemOut(_CamelModel):
    id: Union[int, str]
    type: Literal["system", "screening", "training", "refer"] = "system"
    title: str = ""
    content: str = ""
    read: bool = False
    created_at: str = ""


class NotificationListOut(_CamelModel):
    total: int
    unread: int
    list: List[NotificationItemOut] = Field(default_factory=list)


class NotificationReadParams(_CamelModel):
    ids: List[Union[int, str]] = Field(default_factory=list)


# ====================== 公告（管理类） ======================

class NoticeOut(_CamelModel):
    id: int
    title: str
    summary: str = ""
    content: str = ""
    cover_url: str = ""
    notice_type: str = "SYSTEM"
    status: str = "DRAFT"
    visible_roles: str = ""
    is_top: bool = False
    publisher_id: int = 0
    publisher_name: str = ""
    publish_at: Optional[str] = None
    expire_at: Optional[str] = None
    view_count: int = 0
    created_at: str = ""
    updated_at: str = ""


class NoticePageOut(_CamelModel):
    total: int
    page: int
    page_size: int
    list: List[NoticeOut] = Field(default_factory=list)


class NoticeSaveParams(_CamelModel):
    title: str = Field(..., min_length=1, max_length=128)
    summary: Optional[str] = Field(None, max_length=255)
    content: str = Field(..., min_length=1)
    cover_url: Optional[str] = Field(None, max_length=255)
    notice_type: Optional[Literal["SYSTEM", "TRAINING", "SCREENING", "EXAM"]] = "SYSTEM"
    status: Optional[Literal["DRAFT", "PUBLISHED", "ARCHIVED"]] = "DRAFT"
    visible_roles: Optional[str] = Field(None, max_length=64)
    is_top: Optional[bool] = False
    publish_at: Optional[str] = None
    expire_at: Optional[str] = None


# ====================== 操作日志 ======================

class OperationLogOut(_CamelModel):
    id: int
    user_id: Optional[int] = None
    username: str = ""
    module: str = ""
    action: str = ""
    detail: Optional[str] = None
    ip: Optional[str] = None
    created_at: str = ""


class OperationLogPageOut(_CamelModel):
    total: int
    list: List[OperationLogOut] = Field(default_factory=list)


# ====================== 全院培训统计 ======================

class TrainingOverviewItem(_CamelModel):
    label: str
    value: int = 0


class TrainingOverviewOut(_CamelModel):
    total_users: int = 0
    total_cases: int = 0
    total_records: int = 0
    avg_iou: float = 0.0
    pass_rate: float = 0.0
    by_difficulty: List[TrainingOverviewItem] = Field(default_factory=list)
    by_dr_grade: List[TrainingOverviewItem] = Field(default_factory=list)


class StudyHoursItem(_CamelModel):
    user_id: int
    username: str
    real_name: str = ""
    department: str = ""
    total_seconds: int = 0
    total_hours: float = 0.0
    case_count: int = 0
    avg_iou: float = 0.0


class StudyHoursOut(_CamelModel):
    total: int
    list: List[StudyHoursItem] = Field(default_factory=list)


# ====================== 服务器时间 ======================

class ServerTimeOut(_CamelModel):
    time: str
    timezone: str = "Asia/Shanghai"


class PingOut(_CamelModel):
    status: str = "ok"
    time: str = ""


__all__ = [
    "DictItemOut",
    "DictBatchParams",
    "HospitalOut",
    "DepartmentOut",
    "DepartmentSaveParams",
    "SystemConfigOut",
    "UploadFileResultOut",
    "NotificationItemOut",
    "NotificationListOut",
    "NotificationReadParams",
    "NoticeOut",
    "NoticePageOut",
    "NoticeSaveParams",
    "OperationLogOut",
    "OperationLogPageOut",
    "TrainingOverviewItem",
    "TrainingOverviewOut",
    "StudyHoursItem",
    "StudyHoursOut",
    "ServerTimeOut",
    "PingOut",
]
