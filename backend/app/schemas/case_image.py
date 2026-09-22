"""
病例影像（一对多） Pydantic schema
"""
from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


CaseImageRoleLiteral = Literal[
    "original", "MA", "HE", "EX", "SE", "OD",
    "color_mask", "overlay", "class_mask", "other",
]
CaseTableLiteral = Literal["screening", "training"]
EyeSideLiteral = Literal["OD", "OS", "OU", "UK"]


class _CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        arbitrary_types_allowed=True,
    )


class CaseImageOut(_CamelModel):
    id: int
    case_table: CaseTableLiteral
    case_id: int
    role: CaseImageRoleLiteral
    role_text: str = ""
    eye: EyeSideLiteral = "UK"
    file_url: str
    file_name: str = ""
    file_size: int = 0
    width: int = 0
    height: int = 0
    sort_order: int = 0
    uploaded_by: Optional[int] = None
    uploader_name: str = ""
    created_at: Optional[datetime] = None


class CaseImagesGrouped(_CamelModel):
    """按 role 分组返回。前端阅片页直接消费此结构。"""
    case_table: CaseTableLiteral
    case_id: int
    case_sn: str = ""
    case_no: str = ""
    image_groups: Dict[CaseImageRoleLiteral, List[str]] = Field(default_factory=dict)
    items: List[CaseImageOut] = Field(default_factory=list)
    image_complete: bool = True
    missing_roles: List[CaseImageRoleLiteral] = Field(default_factory=list)


class IncompleteCaseRow(_CamelModel):
    case_table: CaseTableLiteral
    case_id: int
    case_no: str = ""
    case_sn: str = ""
    title: str = ""
    missing_roles: List[CaseImageRoleLiteral] = Field(default_factory=list)
    image_count: int = 0


class IncompletePage(_CamelModel):
    total: int = 0
    page: int = 1
    page_size: int = 20
    list: List[IncompleteCaseRow] = Field(default_factory=list)


class IdridImportParams(_CamelModel):
    source_path: Optional[str] = Field(
        None, description="IDRiD 数据集根目录，省略则使用默认路径",
    )
    limit: Optional[int] = Field(None, ge=1)
    dry_run: bool = False
    skip_existing: bool = True


class BackfillPatientParams(_CamelModel):
    only_empty: bool = Field(
        True, description="只补空字段；为 False 时按 overwrite 决定是否覆盖",
    )
    overwrite: bool = Field(
        False,
        description="强制覆盖已有的模拟患者信息。真实采集的信息不会被覆盖 —— "
                    "训练病例本无真实患者，此开关只用于重置模拟数据",
    )


class BackfillPatientResult(_CamelModel):
    training_total: int = 0
    training_filled: int = 0
    screening_total: int = 0
    screening_filled: int = 0
    case_sn_filled: int = Field(0, description="顺带补齐的业务流水号数量")


class IdridImportResult(_CamelModel):
    imported_cases: int = 0
    appended_images: int = 0
    skipped_cases: int = 0
    incomplete_cases: int = 0
    grade_distribution: Dict[str, int] = Field(default_factory=dict)
    elapsed_sec: float = 0.0
    dry_run: bool = False
    sample_case_sns: List[str] = Field(default_factory=list)
    source_path: str = ""


class IdridProbeResult(_CamelModel):
    """探测服务器约定目录是否已放好数据集，不写库。"""
    source_path: str = ""
    default_path: str = ""
    exists: bool = False
    ready: bool = False
    missing_subdirs: List[str] = Field(default_factory=list)
    image_count: int = 0
    train_count: int = 0
    test_count: int = 0
    hint: str = ""


__all__ = [
    "CaseImageOut",
    "CaseImagesGrouped",
    "IncompleteCaseRow",
    "IncompletePage",
    "IdridImportParams",
    "IdridImportResult",
    "IdridProbeResult",
    "BackfillPatientParams",
    "BackfillPatientResult",
    "CaseImageRoleLiteral",
    "CaseTableLiteral",
]
