"""
学习资料 / 收藏 / 学习笔记 模型
- LearningResource：公共学习资料（教师/管理员上传）
- ResourceFavorite：用户收藏关联表
- LearningNote：个人学习笔记（支持绑定病例 / 影像）
"""

from enum import Enum
from typing import Optional

from sqlalchemy import (
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


# ============================================================
# 枚举
# ============================================================

class ResourceTypeEnum(str, Enum):
    """学习资料分类"""
    CASE_TEMPLATE = "CASE_TEMPLATE"   # 病例范本
    COURSEWARE = "COURSEWARE"         # 实训课件
    KNOWLEDGE = "KNOWLEDGE"           # 知识点文档
    IMAGE_DEMO = "IMAGE_DEMO"         # 教学影像


class ResourceStatusEnum(str, Enum):
    DRAFT = "DRAFT"          # 草稿
    PUBLISHED = "PUBLISHED"  # 已发布
    ARCHIVED = "ARCHIVED"    # 已下线


# ============================================================
# 学习资料表
# ============================================================

class LearningResource(Base, TimestampMixin):
    """公共学习资料（教师/管理员维护，全员可见）"""

    __tablename__ = "biz_learning_resource"
    __table_args__ = {"comment": "学习资料表"}

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, comment="资料ID"
    )

    title: Mapped[str] = mapped_column(
        String(160), nullable=False, index=True, comment="资料标题"
    )
    summary: Mapped[str] = mapped_column(
        String(512), nullable=False, default="", comment="简介摘要"
    )
    content: Mapped[str] = mapped_column(
        Text, nullable=False, default="",
        comment="正文（HTML/Markdown，用于在线预览）",
    )
    resource_type: Mapped[str] = mapped_column(
        String(24), nullable=False, default=ResourceTypeEnum.KNOWLEDGE.value,
        index=True,
        comment="分类：CASE_TEMPLATE/COURSEWARE/KNOWLEDGE/IMAGE_DEMO",
    )
    tags: Mapped[str] = mapped_column(
        String(255), nullable=False, default="",
        comment="标签，逗号分隔，例：DR,出血,2级",
    )

    # 资源外链（图片/PDF/视频地址）
    cover_url: Mapped[str] = mapped_column(
        String(512), nullable=False, default="", comment="封面图URL"
    )
    file_url: Mapped[str] = mapped_column(
        String(512), nullable=False, default="",
        comment="附件 URL（PDF / 视频 / 影像范本）",
    )
    file_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="",
        comment="附件类型：pdf/video/image/markdown",
    )

    # 关联病例（可选）
    case_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("biz_training_case.id", ondelete="SET NULL"),
        nullable=True, index=True,
        comment="关联病例ID（可选）",
    )

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ResourceStatusEnum.PUBLISHED.value,
        index=True, comment="状态：DRAFT/PUBLISHED/ARCHIVED",
    )

    publisher_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sys_user.id", ondelete="RESTRICT"),
        nullable=False, comment="发布者ID（教师/管理员）",
    )

    view_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="阅读次数"
    )
    favorite_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="被收藏次数"
    )

    publisher = relationship("User", lazy="joined", foreign_keys=[publisher_id])

    def __repr__(self) -> str:
        return f"<LearningResource #{self.id} {self.title}>"


# ============================================================
# 收藏关联表
# ============================================================

class ResourceFavorite(Base, TimestampMixin):
    """用户 - 资料 收藏关系"""

    __tablename__ = "biz_resource_favorite"
    __table_args__ = (
        UniqueConstraint("user_id", "resource_id", name="uq_user_resource"),
        {"comment": "学习资料收藏关联表"},
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, comment="收藏ID"
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sys_user.id", ondelete="CASCADE"),
        nullable=False, index=True, comment="用户ID",
    )
    resource_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("biz_learning_resource.id", ondelete="CASCADE"),
        nullable=False, index=True, comment="资料ID",
    )
    label: Mapped[str] = mapped_column(
        String(64), nullable=False, default="",
        comment="自定义分类标签（学员自己用）",
    )

    user = relationship("User", lazy="joined", foreign_keys=[user_id])
    resource = relationship(
        "LearningResource", lazy="joined", foreign_keys=[resource_id],
    )

    def __repr__(self) -> str:
        return f"<ResourceFavorite user={self.user_id} resource={self.resource_id}>"


# ============================================================
# 学习笔记表
# ============================================================

class LearningNote(Base, TimestampMixin):
    """学员个人学习笔记，可绑定病例 / 影像"""

    __tablename__ = "biz_learning_note"
    __table_args__ = {"comment": "学习笔记表"}

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, comment="笔记ID"
    )

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sys_user.id", ondelete="CASCADE"),
        nullable=False, index=True, comment="作者用户ID",
    )

    title: Mapped[str] = mapped_column(
        String(160), nullable=False, default="", index=True,
        comment="笔记标题",
    )
    content: Mapped[str] = mapped_column(
        Text, nullable=False, default="", comment="笔记正文",
    )
    tags: Mapped[str] = mapped_column(
        String(255), nullable=False, default="",
        comment="标签，逗号分隔",
    )

    # 关联（可选）
    case_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("biz_training_case.id", ondelete="SET NULL"),
        nullable=True, index=True,
        comment="关联病例ID（可选）",
    )
    image_index: Mapped[int] = mapped_column(
        Integer, nullable=False, default=-1,
        comment="关联影像下标，-1 表示未指定",
    )
    image_url: Mapped[str] = mapped_column(
        String(512), nullable=False, default="",
        comment="关联影像 URL（冗余存档）",
    )
    resource_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("biz_learning_resource.id", ondelete="SET NULL"),
        nullable=True, comment="关联资料ID（可选）",
    )

    user = relationship("User", lazy="joined", foreign_keys=[user_id])
    case = relationship("TrainingCase", lazy="joined", foreign_keys=[case_id])
    resource = relationship(
        "LearningResource", lazy="joined", foreign_keys=[resource_id],
    )

    def __repr__(self) -> str:
        return f"<LearningNote #{self.id} user={self.user_id} title={self.title}>"
