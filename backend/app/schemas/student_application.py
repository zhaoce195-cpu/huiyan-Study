"""学员开户申请 schema（与机构申请分离）"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel


class _CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


_PHONE_RE = r"^1[3-9]\d{9}$"


class StudentAppCreate(_CamelModel):
    real_name: str = Field(..., min_length=1, max_length=32, description="姓名")
    phone: str = Field(..., description="11 位手机号")
    department: str = Field(..., min_length=1, max_length=64, description="科室")
    reason: str = Field(..., min_length=4, max_length=500, description="申请理由")

    @field_validator("phone")
    @classmethod
    def phone_ok(cls, v: str):
        p = (v or "").strip()
        import re
        if not re.match(_PHONE_RE, p):
            raise ValueError("请输入 11 位有效手机号")
        return p

    @field_validator("real_name", "department", "reason")
    @classmethod
    def strip_text(cls, v: str):
        return (v or "").strip()


class StudentAppReview(_CamelModel):
    accept: bool
    comment: str = Field("", max_length=500, description="通过备注或驳回理由")


class StudentAppOut(_CamelModel):
    id: int
    real_name: str
    phone: str
    department: str = ""
    reason: str = ""
    status: str
    reviewer_id: Optional[int] = None
    reviewer_name: str = ""
    review_comment: str = ""
    reviewed_at: Optional[datetime] = None
    created_user_id: Optional[int] = None
    account_username: Optional[str] = None
    temp_password: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class StudentAppPage(_CamelModel):
    total: int = 0
    page: int = 1
    page_size: int = 20
    list: List[StudentAppOut] = Field(default_factory=list)


class StudentAppStatusOut(_CamelModel):
    """访客按手机号查询进度（不含初密）"""
    found: bool = False
    status: str = ""
    real_name: str = ""
    review_comment: str = ""
    account_username: str = ""
    created_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
