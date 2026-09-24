"""
用户相关请求/响应模型
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from pydantic.alias_generators import to_camel

from app.db.models.user import RoleEnum


# ====================== 入参 ======================

class LoginRequest(BaseModel):
    """登录请求"""
    username: str = Field(..., min_length=2, max_length=64, description="登录账号")
    password: str = Field(..., min_length=6, max_length=64, description="登录密码")
    remember: bool = Field(False, description="记住登录")


class ChangePasswordRequest(BaseModel):
    """修改密码请求"""
    old_password: str = Field(..., min_length=6, max_length=64, description="原密码")
    new_password: str = Field(..., min_length=6, max_length=64, description="新密码")
    confirm_password: str = Field(..., min_length=6, max_length=64, description="确认新密码")

    @field_validator("confirm_password")
    @classmethod
    def confirm_match(cls, v: str, info):
        new_pwd = info.data.get("new_password")
        if new_pwd and v != new_pwd:
            raise ValueError("两次输入的新密码不一致")
        return v

    @field_validator("new_password")
    @classmethod
    def new_password_strength(cls, v: str):
        if len(v) < 6:
            raise ValueError("新密码长度不能少于 6 位")
        if v.isdigit() or v.isalpha():
            raise ValueError("密码需包含字母与数字组合，提升账号安全")
        return v


class UserUpdateRequest(BaseModel):
    """修改个人资料"""
    real_name: Optional[str] = Field(None, max_length=32, description="真实姓名")
    phone: Optional[str] = Field(None, max_length=20, description="手机号")
    email: Optional[EmailStr] = Field(None, description="邮箱")
    department: Optional[str] = Field(None, max_length=64, description="所属科室")
    title: Optional[str] = Field(None, max_length=32, description="职称")


# ====================== 出参 ======================

class UserOut(BaseModel):
    """用户基础信息"""
    id: int
    username: str
    real_name: str = ""
    phone: str = ""
    email: str = ""
    department: str = ""
    title: str = ""
    avatar: str = ""

    role: RoleEnum
    role_name: str = ""
    user_type: str = ""

    is_active: bool
    must_change_password: bool = False
    last_login_at: Optional[datetime] = None
    last_login_ip: str = ""

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ====================== 管理员 · 用户账号 ======================

class _CamelUser(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class AdminUserItem(_CamelUser):
    id: int
    username: str
    real_name: str = ""
    role: str = ""
    role_name: str = ""
    department: str = ""
    hospital_name: str = ""
    is_active: bool = True
    must_change_password: bool = False
    last_login_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class AdminUserPage(_CamelUser):
    total: int = 0
    page: int = 1
    page_size: int = 20
    list: List[AdminUserItem] = Field(default_factory=list)


class AdminUserCreate(_CamelUser):
    username: str = Field(..., min_length=2, max_length=32, description="登录账号")
    real_name: str = Field(..., min_length=1, max_length=32, description="真实姓名")
    role: RoleEnum = Field(..., description="STUDENT / TEACHER / ADMIN")
    department: str = Field("", max_length=64, description="所属科室")
    department_id: Optional[int] = Field(None, description="所属科室记录，用来把同名科室按医院分开")
    password: str = Field(..., min_length=6, max_length=64, description="初始密码")

    @field_validator("username")
    @classmethod
    def username_format(cls, v: str):
        name = (v or "").strip()
        if not name:
            raise ValueError("账号不能为空")
        if " " in name:
            raise ValueError("账号不能包含空格")
        return name

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str):
        if v.isdigit() or v.isalpha():
            raise ValueError("密码需包含字母与数字组合")
        return v

    @field_validator("role")
    @classmethod
    def role_allowed(cls, v: RoleEnum):
        if v not in (RoleEnum.STUDENT, RoleEnum.TEACHER, RoleEnum.ADMIN):
            raise ValueError("角色只能是 STUDENT / TEACHER / ADMIN")
        return v


class AdminSetActiveParams(_CamelUser):
    is_active: bool = Field(..., description="True=启用，False=停用")


class AdminResetPasswordOut(_CamelUser):
    user_id: int
    username: str
    temp_password: str
    must_change_password: bool = True


class LoginResponse(BaseModel):
    """登录返回"""
    token: str = Field(..., description="访问令牌")
    token_type: str = Field("Bearer", description="令牌类型")
    expires_at: datetime = Field(..., description="令牌到期时间")
    user_info: UserOut = Field(..., description="用户信息")


class AvatarUploadResponse(BaseModel):
    """头像上传响应"""
    avatar_url: str = Field(..., description="头像访问 URL")
    file_name: str = Field(..., description="存储文件名")
    file_size: int = Field(..., description="文件字节数")


# ====================== 微信小程序登录 ======================

class WechatLoginRequest(BaseModel):
    """微信小程序静默登录：wx.login 拿到的 code"""
    code: str = Field(..., min_length=1, max_length=256, description="wx.login 返回的 code")


class WechatBindRequest(BaseModel):
    """微信首次绑定：临时票据 + 已有账号密码"""
    ticket: str = Field(..., min_length=1, description="login 接口返回的绑定票据")
    username: str = Field(..., min_length=2, max_length=64, description="已有平台账号")
    password: str = Field(..., min_length=6, max_length=64, description="账号密码")


class WechatLoginResponse(BaseModel):
    """
    微信登录返回：
    - need_bind=False：openid 已绑定账号，login 字段为正式登录态
    - need_bind=True ：openid 未绑定，前端引导用户用 ticket + 账号密码绑定
    """
    need_bind: bool = Field(..., description="是否需要绑定已有账号")
    ticket: str = Field("", description="未绑定时下发的临时绑定票据")
    login: Optional[LoginResponse] = Field(None, description="已绑定时的登录态")
