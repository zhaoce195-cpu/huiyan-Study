"""
病例浏览检索模块 Pydantic schema
- 提供统一的病例检索/详情/归档接口字段
- 通过 alias_generator=to_camel 输出 camelCase
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


CategoryLiteral = Literal["DR", "AMD", "GLAUCOMA", "HYPERTENSION", "NORMAL", "OTHER"]
ArchiveStatusLiteral = Literal["ACTIVE", "ARCHIVED"]
CreatorRoleLiteral = Literal["STUDENT", "TEACHER", "ADMIN"]


class CaseBrowseQuery(_CamelModel):
    """病例检索查询参数"""
    keyword: Optional[str] = Field(None, description="关键词（编号/姓名/手机号/标题/描述/创建人/case_sn）")
    category: Optional[CategoryLiteral] = Field(None, description="病种分类")
    dr_level: Optional[int] = Field(None, ge=0, le=4, description="DR 严重等级 0~4")
    difficulty: Optional[str] = Field(None, description="难度：EASY/MEDIUM/HARD")
    archive_status: Optional[ArchiveStatusLiteral] = Field(None, description="归档状态")
    creator_role: Optional[CreatorRoleLiteral] = Field(None, description="创建人员角色")
    start_time: Optional[datetime] = Field(None, description="上传起始时间")
    end_time: Optional[datetime] = Field(None, description="上传结束时间")
    only_incomplete: bool = Field(False, description="只看影像不完整的病例")
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=200)


class CaseBrowseItem(_CamelModel):
    """病例列表项"""
    id: int
    case_no: str = Field(..., description="病例编号")
    case_sn: str = ""
    title: str = ""
    description: str = ""
    category: CategoryLiteral = "DR"
    category_text: str = ""
    difficulty: str = ""
    difficulty_text: str = ""
    # 盲训态下为 None（未解锁）；同时用于区分「不适用」与「0 级无 DR」
    dr_level: Optional[int] = None
    dr_grade_text: str = ""
    archive_status: ArchiveStatusLiteral = "ACTIVE"
    is_published: bool = False
    is_train_case: bool = Field(False, description="是否已加入实训库（学员端可见性）")
    creator_id: int = 0
    creator_name: str = ""
    creator_role: str = ""
    thumb_url: Optional[str] = None
    image_count: int = 0
    image_complete: bool = True
    missing_roles: List[str] = Field(default_factory=list)
    # ============ 模拟患者信息（按调用者角色脱敏） ============
    patient_name: str = ""
    patient_gender: str = "U"
    patient_age: int = 0
    patient_phone: str = Field("", description="完整手机号或 mask 后的字符串，由后端按角色返回")
    phone_visible: bool = Field(True, description="当前调用者是否可见完整手机号")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CaseBrowsePage(_CamelModel):
    total: int = 0
    page: int = 1
    page_size: int = 20
    list: List[CaseBrowseItem] = Field(default_factory=list)


class CaseBrowseDetail(CaseBrowseItem):
    """病例详情"""
    clinical_info: str = ""
    image_paths: dict = Field(default_factory=dict)
    images: List[str] = Field(default_factory=list, description="平铺所有眼底图地址")
    gold_diagnosis: str = ""
    teaching_points: str = ""
    pass_score: int = 60


class CaseArchiveParams(_CamelModel):
    archive_status: ArchiveStatusLiteral = Field(..., description="目标状态")
    reason: Optional[str] = Field(None, description="归档原因（可选）")
