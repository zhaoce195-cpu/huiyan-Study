"""
机构申请 / 用户站内消息 Pydantic schema
- 与前端 frontend/src/api/organization.ts / user-message.ts 一一对应
- 通过 alias_generator=to_camel 自动驼峰输出
"""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class _CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        arbitrary_types_allowed=True,
    )


# ====================== 机构 ======================

class OrganizationOut(_CamelModel):
    id: int
    name: str
    code: str = ""
    category: str = ""
    address: str = ""
    contact: str = ""
    phone: str = ""
    description: str = ""
    is_active: bool = True


# ====================== 申请 ======================

class OrgApplicationCreate(_CamelModel):
    organization_id: int = Field(..., ge=1)
    reason: str = Field("", max_length=500)


class OrgApplicationReview(_CamelModel):
    accept: bool
    comment: str = Field("", max_length=500)


class OrgApplicationOut(_CamelModel):
    id: int
    applicant_id: int
    applicant_name: str = ""
    applicant_phone: str = ""
    organization_id: int
    organization_name: str = ""
    reason: str = ""
    status: Literal["PENDING", "APPROVED", "REJECTED"]
    reviewer_id: Optional[int] = None
    reviewer_name: str = ""
    review_comment: str = ""
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class OrgApplicationPage(_CamelModel):
    total: int
    page: int
    page_size: int
    list: List[OrgApplicationOut] = Field(default_factory=list)


# ====================== 用户消息 ======================

class UserMessageOut(_CamelModel):
    id: int
    type: str
    title: str
    content: str
    ref_type: str = ""
    ref_id: Optional[int] = None
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime


class UserMessagePage(_CamelModel):
    total: int
    unread: int
    page: int
    page_size: int
    list: List[UserMessageOut] = Field(default_factory=list)


class UserMessageReadParams(_CamelModel):
    ids: List[int] = Field(default_factory=list)
