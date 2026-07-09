"""
Pydantic schemas 统一出口
"""

from app.schemas.user import (  # noqa: F401
    LoginRequest,
    LoginResponse,
    UserOut,
    UserUpdateRequest,
    ChangePasswordRequest,
    AvatarUploadResponse,
)
from app.schemas.setting import (  # noqa: F401
    UserSettingOut,
    UserSettingUpdateRequest,
)
