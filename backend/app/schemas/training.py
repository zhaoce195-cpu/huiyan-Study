"""
实训培训模块 Pydantic schema
- 与前端 frontend/src/api/training.ts 字段一一对应
- 通过 alias_generator=to_camel 自动把 snake_case 转 camelCase 输出
- 前端调用时传 camelCase，后端落库时仍是 snake_case（数据库无影响）
"""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


# ====================== 公共 ======================

class _CamelModel(BaseModel):
    """所有训练模块 schema 的基类：camelCase 别名 + 任意名称都接受"""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        arbitrary_types_allowed=True,
    )


GradeLiteral = Literal["A+", "A", "B", "C"]
DifficultyLiteral = Literal["入门", "初级", "中级", "高级"]
LesionLiteral = Literal["出血", "渗出", "微动脉瘤", "棉绒斑", "新生血管"]
EyeSideLiteral = Literal["OD", "OS", "OU"]
GenderLiteral = Literal["男", "女"]
AnnotationTypeLiteral = Literal["rect", "polygon", "pen"]
DRLevelLiteral = Literal[0, 1, 2, 3, 4]


# ====================== 通用结构 ======================

class Lesion(_CamelModel):
    type: LesionLiteral = Field(..., description="病灶分类")
    count: int = Field(..., ge=0, description="病灶数量")
    location: str = Field("", description="病灶位置描述")


class AnnotationPoint(_CamelModel):
    x: float
    y: float


class Annotation(_CamelModel):
    id: str = Field(..., description="客户端临时ID")
    server_id: Optional[str] = Field(None, description="服务端ID")
    type: AnnotationTypeLiteral = Field(..., description="标注类型")
    points: List[AnnotationPoint] = Field(default_factory=list, description="像素坐标点")
    label: LesionLiteral = Field(..., description="病灶分类")
    color: Optional[str] = Field(None, description="前端展示色")
    remark: Optional[str] = Field(None, description="备注")


# ====================== 病例 ======================

class CaseListQuery(_CamelModel):
    keyword: Optional[str] = None
    dr_level: Optional[DRLevelLiteral] = Field(None, description="DR分级")
    difficulty: Optional[DifficultyLiteral] = None
    done: Optional[bool] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(100, ge=1, le=500)


class TrainingCaseOut(_CamelModel):
    """病例列表/详情统一出参"""
    id: str = Field(..., description="病例编号 CASE001")
    name: str = Field("", description="患者姓名（脱敏）")
    age: int = 0
    gender: GenderLiteral = Field("男")
    eye: EyeSideLiteral = Field("OU")
    dr_grade: str = Field("", description="DR分级文本：4 级 PDR")
    dr_level: DRLevelLiteral = 0
    difficulty: DifficultyLiteral = "入门"
    done: bool = False
    thumb_url: Optional[str] = None
    image_url: Optional[str] = None
    diabetes_years: int = 0
    hospital: str = ""
    best_iou: Optional[float] = None
    lesions: List[Lesion] = Field(default_factory=list)
    created_at: Optional[str] = None


class PageResult(_CamelModel):
    total: int
    page: int
    page_size: int
    list: List[TrainingCaseOut]


# ====================== 标注 / IoU ======================

class SubmitAnnotationParams(_CamelModel):
    case_id: str = Field(..., description="病例编号")
    canvas_width: int = Field(..., gt=0, description="画布宽")
    canvas_height: int = Field(..., gt=0, description="画布高")
    annotations: List[Annotation] = Field(default_factory=list)
    duration_sec: Optional[int] = Field(None, ge=0, description="标注耗时秒")


class IoUDetail(_CamelModel):
    label: LesionLiteral
    iou: float = Field(..., ge=0, le=1)
    recall: int = 0
    missed: int = 0
    false_positive: int = 0


class IoUResult(_CamelModel):
    case_id: str
    iou: float = Field(..., ge=0, le=1)
    details: List[IoUDetail] = Field(default_factory=list)
    grade: GradeLiteral = "C"
    comment: str = ""
    submitted_at: str


# ====================== 热力图 / 金标准 ======================

class Hotspot(_CamelModel):
    x: float
    y: float
    radius: float
    score: float
    label: Optional[LesionLiteral] = None


class HeatmapResult(_CamelModel):
    case_id: str
    heatmap_url: str
    hotspots: List[Hotspot] = Field(default_factory=list)


class GoldStandardResult(_CamelModel):
    case_id: str
    annotations: List[Annotation] = Field(default_factory=list)


# ====================== 统计 ======================

class TrainingStats(_CamelModel):
    total_cases: int = 0
    done_cases: int = 0
    avg_iou: float = Field(0.0, alias="avgIoU")
    best_iou: float = Field(0.0, alias="bestIoU")
    total_annotations: int = 0
    total_duration: int = Field(0, description="总耗时（秒）")


__all__ = [
    "Lesion",
    "AnnotationPoint",
    "Annotation",
    "CaseListQuery",
    "TrainingCaseOut",
    "PageResult",
    "SubmitAnnotationParams",
    "IoUDetail",
    "IoUResult",
    "Hotspot",
    "HeatmapResult",
    "GoldStandardResult",
    "TrainingStats",
]
