"""
影像阅片模块 Pydantic schema
- 影像源数据查询
- 阅片标注集合的保存、查询、提交、审核
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


# 工具类型枚举
ToolLiteral = Literal["rect", "polygon", "pen", "length", "angle", "freehand", "ellipse"]
# REJECTED：驳回是独立状态，不倒回 DRAFT，否则分不出
# 「学员还没写完」和「提交过但被驳回」。合法流转见 app.common.workflow
StatusLiteral = Literal["DRAFT", "SUBMITTED", "REVIEWED", "REJECTED"]


# ====================== 影像源 ======================

class ImageSource(_CamelModel):
    """病例影像源信息"""
    case_id: int
    case_no: str
    case_sn: str = ""
    width: int = 0
    height: int = 0
    images: List[str] = Field(default_factory=list, description="平铺所有眼底图地址")
    image_meta: List[Dict[str, Any]] = Field(
        default_factory=list,
        description='每张影像元信息 [{"index":0,"url":"...","side":"OD"}, ...]',
    )
    # ============ 一对多影像扩展（兼容旧客户端：旧字段保留） ============
    image_groups: Dict[str, List[str]] = Field(
        default_factory=dict,
        description='按 role 分组：{"original":[...],"MA":[...],"HE":[...],"overlay":[...]}',
    )
    image_complete: bool = True
    missing_roles: List[str] = Field(default_factory=list)
    show_gold_layers: bool = False

    # 影像 URL → PACS 中对应 DICOM 实例的 UID。
    # 只收录在 PACS 中确实核对到的那些：对不上就不给，前端退回 JPG。
    # 宁可某个病例暂时不走 DICOM，也不能把影像与标注配错。
    dicom_instances: Dict[str, Dict[str, str]] = Field(
        default_factory=dict,
        description="影像 URL → {studyInstanceUid, seriesInstanceUid, sopInstanceUid}",
    )
    # 金标准的像素级分割。学员未解锁金标准时不下发 ——
    # 光是把 SOP UID 递出去，就等于给了取答案的入口。
    segmentation: Optional[Dict[str, Any]] = Field(
        None, description="DICOM SEG：{sopInstanceUid, segments:[{number,label}]}",
    )

    # ============ 安全标识（报告 P0/P1：安全条常驻） ============
    modality: str = Field("CFP", description="影像模态编码")
    modality_text: str = Field("眼底彩照", description="影像模态中文名")
    exam_date: Optional[datetime] = Field(
        None, description="检查日期；为空表示原始数据未采集，前端须显式提示未知",
    )
    exam_date_known: bool = Field(
        False, description="检查日期是否可信。为 False 时不得用入库时间冒充检查日期",
    )
    safety: Dict[str, Any] = Field(
        default_factory=dict,
        description="病例级安全汇总：原图张数、派生对象数、眼别集合、眼别冲突",
    )
    # ============ 模拟患者信息（按调用者角色脱敏） ============
    patient_name: str = ""
    patient_gender: str = "U"
    patient_age: int = 0
    patient_phone: str = ""
    phone_visible: bool = True


# ====================== 标注 ======================

class Point2D(_CamelModel):
    x: float
    y: float


class AnnotationItem(_CamelModel):
    id: str = Field(..., description="客户端临时ID或服务端ID")
    tool: ToolLiteral
    points: List[Point2D] = Field(default_factory=list)
    label: str = Field("", description="病灶标签或备注标签")
    color: Optional[str] = None
    layer: str = Field("primary", description="所属图层")
    remark: str = ""
    # 测量结果（length / angle）
    value: Optional[float] = Field(None, description="距离（像素）或角度（度）")
    unit: Optional[str] = Field(None, description="px / °")


class ViewportState(_CamelModel):
    scale: float = 1.0
    x: float = 0.0
    y: float = 0.0
    ww: float = Field(255.0, description="窗宽")
    wl: float = Field(127.0, description="窗位")
    invert: bool = False
    # 产生这份快照的渲染内核。legacy（缺省）的 scale=1 是影像 1:1 显示，
    # cs3d 的 zoom=1 是适配窗口，两者不同量纲。缺标记的旧快照
    # 只还原窗宽窗位，缩放平移重置为适配，避免明显错位。
    engine: str = Field("legacy", description="渲染内核：legacy / cs3d")


class LayerState(_CamelModel):
    primary: bool = True
    heatmap: bool = False
    gold: bool = False
    my: bool = True


# ====================== 入参 ======================

class ReadingSaveParams(_CamelModel):
    case_id: int = Field(..., description="病例 PK 主键 ID")
    image_index: int = 0
    image_url: str = ""
    annotations: List[AnnotationItem] = Field(default_factory=list)
    measurements: List[AnnotationItem] = Field(default_factory=list)
    viewport: Optional[ViewportState] = None
    layers: Optional[LayerState] = None
    diagnosis: Dict[str, Any] = Field(
        default_factory=dict,
        description="结构化诊断结论，键为病种表单的字段 key",
    )
    note: str = ""
    submit: bool = Field(False, description="True 表示提交（SUBMITTED），否则保留为 DRAFT")
    request_id: str = Field(
        "",
        max_length=64,
        description="提交幂等键：断网重试时原样带回，同键回放原记录而非新建一条",
    )


class ReadingReviewParams(_CamelModel):
    review_comment: str = Field("", description="审核意见")
    accept: bool = Field(True, description="True=通过 False=驳回")


# ====================== 出参 ======================

class ReadingOut(_CamelModel):
    id: int
    case_id: int
    case_no: str = ""
    user_id: int
    user_name: str = ""
    image_index: int = 0
    image_url: str = ""
    viewport: Optional[Dict[str, Any]] = None
    annotations: List[Dict[str, Any]] = Field(default_factory=list)
    measurements: List[Dict[str, Any]] = Field(default_factory=list)
    layers: Optional[Dict[str, Any]] = None
    status: StatusLiteral = "DRAFT"
    note: str = ""
    review_comment: str = ""
    reviewer_id: Optional[int] = None
    reviewer_name: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    diagnosis: Dict[str, Any] = Field(default_factory=dict)



class ReadingPage(_CamelModel):
    total: int = 0
    page: int = 1
    page_size: int = 20
    list: List[ReadingOut] = Field(default_factory=list)


class ReadingListQuery(_CamelModel):
    case_id: Optional[int] = None
    user_id: Optional[int] = None
    status: Optional[StatusLiteral] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=200)
