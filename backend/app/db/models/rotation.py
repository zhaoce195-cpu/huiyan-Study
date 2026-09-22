# -*- coding: utf-8 -*-
"""本轮转必做：教师布置的病例和知识点，学员首页用来看截止日期和进度。"""

from enum import Enum
from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class RotationStatusEnum(str, Enum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class RotationTaskKindEnum(str, Enum):
    CASE = "CASE"
    KNOWLEDGE = "KNOWLEDGE"


class Rotation(Base, TimestampMixin):
    __tablename__ = "biz_rotation"
    __table_args__ = {"comment": "轮转学习计划"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(80), nullable=False, default="本轮转")
    start_on: Mapped[str] = mapped_column(String(10), nullable=False, default="")
    due_on: Mapped[str] = mapped_column(String(10), nullable=False, default="")
    pass_score: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=RotationStatusEnum.ACTIVE.value, index=True,
    )
    creator_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sys_user.id", ondelete="RESTRICT"), nullable=False,
    )


class RotationTask(Base, TimestampMixin):
    __tablename__ = "biz_rotation_task"
    __table_args__ = {"comment": "轮转必做项"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rotation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("biz_rotation.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default=RotationTaskKindEnum.CASE.value)
    case_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("biz_training_case.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
    resource_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("biz_learning_resource.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    pass_score: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    due_on: Mapped[str] = mapped_column(String(10), nullable=False, default="")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class RotationTaskAck(Base, TimestampMixin):
    """知识点「已学习」。病例是否合格不记在这里，按练习交卷成绩计算。"""

    __tablename__ = "biz_rotation_task_ack"
    __table_args__ = (
        UniqueConstraint("task_id", "user_id", name="uq_rotation_ack"),
        {"comment": "轮转知识点完成记录"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("biz_rotation_task.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sys_user.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
