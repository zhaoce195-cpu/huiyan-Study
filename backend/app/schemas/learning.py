"""
学习资料 / 收藏 / 笔记 Pydantic schema
- 与前端 frontend/src/api/learning.ts 对齐
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


ResourceTypeLiteral = Literal["CASE_TEMPLATE", "COURSEWARE", "KNOWLEDGE", "IMAGE_DEMO"]
ResourceStatusLiteral = Literal["DRAFT", "PUBLISHED", "ARCHIVED"]


# ====================== 资料 ======================

class ResourceCreateParams(_CamelModel):
    title: str = Field(..., min_length=1, max_length=160)
    summary: str = ""
    content: str = ""
    resource_type: ResourceTypeLiteral = "KNOWLEDGE"
    tags: str = ""
    cover_url: str = ""
    file_url: str = ""
    file_type: str = ""
    case_id: Optional[int] = None
    status: ResourceStatusLiteral = "PUBLISHED"


class ResourceUpdateParams(_CamelModel):
    title: Optional[str] = Field(None, min_length=1, max_length=160)
    summary: Optional[str] = None
    content: Optional[str] = None
    resource_type: Optional[ResourceTypeLiteral] = None
    tags: Optional[str] = None
    cover_url: Optional[str] = None
    file_url: Optional[str] = None
    file_type: Optional[str] = None
    case_id: Optional[int] = None
    status: Optional[ResourceStatusLiteral] = None


class ResourceListQuery(_CamelModel):
    keyword: Optional[str] = None
    resource_type: Optional[ResourceTypeLiteral] = None
    status: Optional[ResourceStatusLiteral] = None
    only_mine: bool = False
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=200)


class ResourceOut(_CamelModel):
    id: int
    title: str
    summary: str = ""
    content: str = ""
    resource_type: ResourceTypeLiteral = "KNOWLEDGE"
    resource_type_text: str = ""
    tags: str = ""
    cover_url: str = ""
    file_url: str = ""
    file_type: str = ""
    case_id: Optional[int] = None
    status: ResourceStatusLiteral = "PUBLISHED"
    publisher_id: int
    publisher_name: str = ""
    view_count: int = 0
    favorite_count: int = 0
    is_favorited: bool = False
    favorite_label: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ResourcePage(_CamelModel):
    total: int = 0
    page: int = 1
    page_size: int = 20
    list: List[ResourceOut] = Field(default_factory=list)


# ====================== 收藏 ======================

class FavoriteParams(_CamelModel):
    resource_id: int
    label: str = ""


class FavoriteListQuery(_CamelModel):
    keyword: Optional[str] = None
    resource_type: Optional[ResourceTypeLiteral] = None
    label: Optional[str] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=200)


# ====================== 笔记 ======================

class NoteCreateParams(_CamelModel):
    title: str = ""
    content: str = ""
    tags: str = ""
    case_id: Optional[int] = None
    image_index: int = -1
    image_url: str = ""
    resource_id: Optional[int] = None


class NoteUpdateParams(_CamelModel):
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[str] = None
    case_id: Optional[int] = None
    image_index: Optional[int] = None
    image_url: Optional[str] = None
    resource_id: Optional[int] = None


class NoteListQuery(_CamelModel):
    keyword: Optional[str] = None
    case_id: Optional[int] = None
    resource_id: Optional[int] = None
    user_id: Optional[int] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=200)


class NoteOut(_CamelModel):
    id: int
    user_id: int
    user_name: str = ""
    title: str = ""
    content: str = ""
    tags: str = ""
    case_id: Optional[int] = None
    case_no: str = ""
    case_title: str = ""
    image_index: int = -1
    image_url: str = ""
    resource_id: Optional[int] = None
    resource_title: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class NotePage(_CamelModel):
    total: int = 0
    page: int = 1
    page_size: int = 20
    list: List[NoteOut] = Field(default_factory=list)
