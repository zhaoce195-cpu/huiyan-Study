"""
用户个性化配置请求/响应模型
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.user_setting import FontSizeEnum, ThemeEnum


class UserSettingOut(BaseModel):
    """用户配置 — 出参"""
    theme: ThemeEnum = ThemeEnum.LIGHT
    font_size: FontSizeEnum = FontSizeEnum.NORMAL
    language: str = "zh-CN"

    notify_message: bool = True
    notify_email: bool = False
    notify_sms: bool = False
    notify_sound: bool = True

    model_config = ConfigDict(from_attributes=True)


class UserSettingUpdateRequest(BaseModel):
    """用户配置 — 入参，全部可选，按字段增量更新"""
    theme: Optional[ThemeEnum] = Field(None, description="主题：light/dark/auto")
    font_size: Optional[FontSizeEnum] = Field(None, description="字体大小：small/normal/large")
    language: Optional[str] = Field(None, max_length=16, description="界面语言")

    notify_message: Optional[bool] = Field(None, description="站内消息通知")
    notify_email: Optional[bool] = Field(None, description="邮件通知")
    notify_sms: Optional[bool] = Field(None, description="短信通知")
    notify_sound: Optional[bool] = Field(None, description="消息提示音")
