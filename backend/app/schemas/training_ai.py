"""
实训病例 AI 辅助诊断 schema
- 与前端 frontend/src/api/training.ts 中 AiDiagnosisResult 对齐
- camelCase 输出（沿用训练模块基类约定）
"""

from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class _CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class AiEyeResult(_CamelModel):
    """单眼 AI 结果"""
    grade: int = Field(0, ge=0, le=4, description="分级/分类编号（DR 0~4；青光眼 0/1）")
    grade_text: str = Field("", description="分级中文描述")
    label: str = Field("", description="展示用文本（病种无关，如 DR 2 级 / 青光眼疑似）")
    image_url: str = Field("", description="送检原图 URL")
    heatmap_url: str = Field("", description="GradCAM 热力图 URL")


class AiProb(_CamelModel):
    """分类任务的类别概率（如青光眼：青光眼疑似 / 正常）"""
    label: str = Field("", description="类别中文名")
    value: float = Field(0.0, description="概率 0~1")


class AiDiagnosisOut(_CamelModel):
    """实训病例 AI 辅助诊断结果"""
    case_id: str = Field(..., description="病例编号 case_no")
    category: str = Field("DR", description="诊断病种：DR / GLAUCOMA / MA ...")
    probs: list[AiProb] = Field(default_factory=list, description="各类别概率（分类任务用，如青光眼）")
    overall_grade: int = Field(0, description="分级/分类编号（DR 0~4；青光眼 0/1）")
    overall_grade_text: str = Field("", description="综合分级中文描述")
    overall_label: str = Field("", description="综合结论展示文本（病种无关，前端优先用它）")
    left: AiEyeResult = Field(default_factory=AiEyeResult, description="左眼 OS")
    right: AiEyeResult = Field(default_factory=AiEyeResult, description="右眼 OD")
    single_eye: bool = Field(False, description="是否单图病例（左右眼使用同一张图）")
    # 前端据此决定渲染几张卡、怎么标注眼别。
    # 以前写死渲染 left + right 两张，只有 OD 的病例会把右眼片子标成「左眼 OS」——
    # 把右眼影像当左眼展示是错误信息，不是显示瑕疵。
    eye_cards: list[str] = Field(
        default_factory=lambda: ["left", "right"],
        description="要展示的眼别卡：left=左眼OS / right=右眼OD / ou=双眼单图",
    )

    # 教学对比
    gold_grade: Optional[int] = Field(None, description="金标准 DR 分级（青光眼为空）")
    gold_label: str = Field("", description="金标准展示文本（病种无关）")
    agree_with_gold: Optional[bool] = Field(None, description="AI 结论是否与金标准一致")

    model_name: str = Field("CSU-EYES DR", description="模型名称")
    infer_duration_ms: int = Field(0, description="推理耗时（毫秒）")
    cached: bool = Field(False, description="是否命中缓存（未重新推理）")
    inferred_at: str = Field("", description="推理时间")


class AiCaseDraftOut(_CamelModel):
    """AI 智能建案结果（教师端）"""
    case_id: str = Field(..., description="新建实训病例编号")
    title: str = Field("", description="病例标题")
    is_published: bool = Field(False, description="是否已发布（建案默认草稿）")
    ai: AiDiagnosisOut = Field(..., description="AI 诊断结果")


__all__ = ["AiEyeResult", "AiProb", "AiDiagnosisOut", "AiCaseDraftOut"]
