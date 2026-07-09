"""
个人中心业务逻辑
"""

from typing import Optional

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.common.utils import delete_avatar_file, save_avatar
from app.core.security import hash_password, verify_password
from app.db.models import User, UserSetting
from app.schemas.setting import UserSettingOut, UserSettingUpdateRequest
from app.schemas.user import (
    AvatarUploadResponse,
    ChangePasswordRequest,
    UserOut,
    UserUpdateRequest,
)
from app.services.auth_service import _build_user_out


class UserService:
    """用户个人中心业务"""

    # ============ 个人资料 ============

    @staticmethod
    def get_profile(user: User) -> UserOut:
        return _build_user_out(user)

    @staticmethod
    def update_profile(
        db: Session, user: User, params: UserUpdateRequest
    ) -> UserOut:
        update_data = params.model_dump(exclude_unset=True, exclude_none=True)
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请至少修改一项信息",
            )
        for field, value in update_data.items():
            setattr(user, field, value)
        db.commit()
        db.refresh(user)
        return _build_user_out(user)

    # ============ 修改密码 ============

    @staticmethod
    def change_password(
        db: Session, user: User, params: ChangePasswordRequest
    ) -> None:
        if not verify_password(params.old_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="原密码不正确",
            )
        if params.old_password == params.new_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="新密码不能与原密码相同",
            )
        user.password_hash = hash_password(params.new_password)
        db.commit()

    # ============ 头像上传 ============

    @staticmethod
    async def update_avatar(
        db: Session, user: User, file: UploadFile
    ) -> AvatarUploadResponse:
        # 删除旧头像
        old = user.avatar
        url, name, size = await save_avatar(file, user.id)
        user.avatar = url
        db.commit()
        if old and old != url:
            delete_avatar_file(old)
        return AvatarUploadResponse(
            avatar_url=url,
            file_name=name,
            file_size=size,
        )

    # ============ 个性化配置 ============

    @staticmethod
    def get_setting(db: Session, user: User) -> UserSettingOut:
        setting: Optional[UserSetting] = user.setting
        if not setting:
            # 兜底：首次访问时初始化
            setting = UserSetting(user_id=user.id)
            db.add(setting)
            db.commit()
            db.refresh(setting)
        return UserSettingOut.model_validate(setting)

    @staticmethod
    def update_setting(
        db: Session,
        user: User,
        params: UserSettingUpdateRequest,
    ) -> UserSettingOut:
        setting: Optional[UserSetting] = user.setting
        if not setting:
            setting = UserSetting(user_id=user.id)
            db.add(setting)
            db.flush()

        update_data = params.model_dump(exclude_unset=True, exclude_none=True)
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请至少修改一项配置",
            )
        for field, value in update_data.items():
            # 枚举值取 .value
            setattr(setting, field, value.value if hasattr(value, "value") else value)
        db.commit()
        db.refresh(setting)
        return UserSettingOut.model_validate(setting)
