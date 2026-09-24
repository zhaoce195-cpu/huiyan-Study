# -*- coding: utf-8 -*-
"""轮转首页：学员看任务和进度，教师布置必做项。"""

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class _Camel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class RotationBrief(_Camel):
    id: int
    title: str
    start_on: str
    due_on: str
    pass_score: int
    total: int
    done: int
    progress: int


class TaskOut(_Camel):
    id: int
    kind: str
    kind_text: str
    title: str
    summary: str = ""
    due_on: str = ""
    pass_score: int = 60
    status: str = "TODO"
    status_text: str = "未开始"
    score: Optional[float] = None
    overdue: bool = False
    due_today: bool = False
    case_id: Optional[int] = None
    case_no: str = ""
    resource_id: Optional[int] = None
    done_count: int = 0
    student_count: int = 0
    tier: str = "REQUIRED"
    scope: str = "ALL"
    scope_value: str = ""
    scope_text: str = "全部"


class StudentTaskSnap(_Camel):
    """教师看到的单项进度，与学员首页用同一套状态。"""
    task_id: int
    status: str
    status_text: str
    score: Optional[float] = None


class StudentProgressOut(_Camel):
    user_id: int
    name: str
    username: str = ""
    study_year: str = ""
    rotation_batch: str = ""
    mentor_group: str = ""
    group_editor_name: str = ""
    group_editor_role: str = ""
    group_edited_at: Optional[str] = None
    done: int
    total: int
    progress: int
    practice_count: int = 0
    completed_cases: int = 0
    avg_score: float = 0.0
    study_seconds: int = 0
    tasks: List[StudentTaskSnap] = Field(default_factory=list)


class WeakLabelBrief(_Camel):
    label: str
    missed: int = 0
    false_positive: int = 0


class GroupSummary(_Camel):
    study_year: str = ""
    rotation_batch: str = ""
    mentor_group: str = ""
    student_count: int = 0
    done: int = 0
    total: int = 0
    progress: int = 0
    weak_labels: List[WeakLabelBrief] = Field(default_factory=list)


class StudentGroupUpdate(_Camel):
    study_year: str = ""
    rotation_batch: str = ""
    mentor_group: str = ""


class StudentHomeOut(_Camel):
    role: Literal["student"] = "student"
    rotation: Optional[RotationBrief] = None
    today: List[TaskOut] = Field(default_factory=list)
    tasks: List[TaskOut] = Field(default_factory=list)
    study_year: str = ""
    rotation_batch: str = ""
    mentor_group: str = ""
    group_editor_name: str = ""
    group_editor_role: str = ""
    group_edited_at: Optional[str] = None


class TeacherHomeOut(_Camel):
    role: Literal["teacher"] = "teacher"
    rotation: Optional[RotationBrief] = None
    tasks: List[TaskOut] = Field(default_factory=list)
    students: List[StudentProgressOut] = Field(default_factory=list)
    groups: List[GroupSummary] = Field(default_factory=list)


class OptionItem(_Camel):
    id: int
    label: str


class RotationOptionsOut(_Camel):
    cases: List[OptionItem] = Field(default_factory=list)
    resources: List[OptionItem] = Field(default_factory=list)


class RotationUpdate(_Camel):
    title: Optional[str] = None
    due_on: Optional[str] = None
    pass_score: Optional[int] = Field(default=None, ge=0, le=100)


class TaskCreate(_Camel):
    kind: Literal["CASE", "KNOWLEDGE"]
    case_id: Optional[int] = None
    resource_id: Optional[int] = None
    title: str = ""
    summary: str = ""
    pass_score: Optional[int] = Field(default=None, ge=0, le=100)
    due_on: str = ""
    tier: Literal["REQUIRED", "EXTENSION"] = "REQUIRED"
    scope: Literal["ALL", "YEAR", "GROUP"] = "ALL"
    scope_value: str = ""


class TaskOrder(_Camel):
    task_ids: List[int] = Field(default_factory=list)
