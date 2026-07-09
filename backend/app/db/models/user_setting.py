"""
用户个性化配置表模型
- 主题模式 / 字体大小 / 消息开关 等
"""

from enum import Enum

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class ThemeEnum(str, Enum):
    LIGHT = "light"
    DARK = "dark"
    AUTO = "auto"


class FontSizeEnum(str, Enum):
    SMALL = "small"
    NORMAL = "normal"
    LARGE = "large"


class UserSetting(Base, TimestampMixin):
    __tablename__ = "sys_user_setting"
    __table_args__ = {"comment": "用户个性化配置表"}

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, comment="配置ID"
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("sys_user.id", ondelete="CASCADE"),
        nullable=False, unique=True,
        comment="用户ID（一对一）",
    )

    # 显示偏好
    theme: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ThemeEnum.LIGHT.value,
        comment="主题模式：light/dark/auto",
    )
    font_size: Mapped[str] = mapped_column(
        String(16), nullable=False, default=FontSizeEnum.NORMAL.value,
        comment="字体大小：small/normal/large",
    )
    language: Mapped[str] = mapped_column(
        String(16), nullable=False, default="zh-CN",
        comment="界面语言",
    )

    # 通知偏好
    notify_message: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="是否开启站内消息通知"
    )
    notify_email: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="是否开启邮件通知"
    )
    notify_sms: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="是否开启短信通知"
    )
    notify_sound: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="是否启用消息提示音"
    )

    # 关系
    user = relationship("User", back_populates="setting")

    def __repr__(self) -> str:
        return f"<UserSetting user_id={self.user_id} theme={self.theme}>"
