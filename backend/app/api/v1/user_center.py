"""
个人中心相关路由（全部需登录）
"""

from fastapi import APIRouter, File, UploadFile

from app.common.response import success
from app.core.dependencies import CurrentUser, DbSession
from app.schemas.setting import UserSettingUpdateRequest
from app.schemas.user import (
    ChangePasswordRequest,
    UserUpdateRequest,
)
from app.services.user_service import UserService

router = APIRouter(prefix="/user", tags=["2. 个人中心"])


# ============== 个人详情 ==============

@router.get(
    "/profile",
    summary="获取当前登录用户详情",
    response_model=None,
)
def get_profile(current_user: CurrentUser):
    data = UserService.get_profile(current_user)
    return success(data=data.model_dump())


@router.put(
    "/profile",
    summary="修改个人资料",
    response_model=None,
)
def update_profile(
    params: UserUpdateRequest,
    current_user: CurrentUser,
    db: DbSession,
):
    data = UserService.update_profile(db=db, user=current_user, params=params)
    return success(data=data.model_dump(), msg="个人资料已更新")


# ============== 密码 ==============

@router.post(
    "/password",
    summary="修改登录密码",
    response_model=None,
)
def change_password(
    params: ChangePasswordRequest,
    current_user: CurrentUser,
    db: DbSession,
):
    UserService.change_password(db=db, user=current_user, params=params)
    return success(msg="密码修改成功，请使用新密码重新登录")


# ============== 头像 ==============

@router.post(
    "/avatar",
    summary="上传 / 更新头像",
    description="支持 jpg/jpeg/png/webp/bmp，最大 5MB；服务器自动压缩为 256×256 webp",
    response_model=None,
)
async def upload_avatar(
    current_user: CurrentUser,
    db: DbSession,
    file: UploadFile = File(..., description="头像图片文件"),
):
    data = await UserService.update_avatar(db=db, user=current_user, file=file)
    return success(data=data.model_dump(), msg="头像更新成功")


# ============== 个性化配置 ==============

@router.get(
    "/setting",
    summary="查询当前用户系统个性化配置",
    response_model=None,
)
def get_setting(current_user: CurrentUser, db: DbSession):
    data = UserService.get_setting(db=db, user=current_user)
    return success(data=data.model_dump())


@router.put(
    "/setting",
    summary="保存 / 修改个性化配置（主题、字体、消息开关）",
    response_model=None,
)
def update_setting(
    params: UserSettingUpdateRequest,
    current_user: CurrentUser,
    db: DbSession,
):
    data = UserService.update_setting(db=db, user=current_user, params=params)
    return success(data=data.model_dump(), msg="个性化配置已保存")
