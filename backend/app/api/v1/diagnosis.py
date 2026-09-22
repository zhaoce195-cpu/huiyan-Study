"""
CSU-EYES 诊断路由（体检筛查端）
==============================
- POST /diagnosis/ma          MA 检测（单图）
- POST /diagnosis/dr          DR 双眼分级
- POST /diagnosis/comprehensive 综合诊断（单图多任务）

权限：医生 / 管理员
返回：DiagnosisOut（含 task_id / 诊断结果 / 标注图URL / 上游原始 JSON）
"""

import base64
import binascii
from io import BytesIO
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from starlette.datastructures import Headers
from starlette.datastructures import UploadFile as StarletteUploadFile

from app.common.response import success
from app.core.dependencies import CurrentUser, DbSession, require_roles
from app.db.models.user import RoleEnum
from app.services.diagnosis_service import DiagnosisService

router = APIRouter(
    prefix="/diagnosis",
    tags=["13. CSU-EYES 智能诊断"],
)

write_dep = Depends(require_roles(RoleEnum.TEACHER, RoleEnum.ADMIN))


def _b64_to_upload(b64: str, filename: str) -> UploadFile:
    """
    把 base64 字符串（可含 data:image/png;base64, 前缀）还原成 UploadFile。
    微信小程序端 wx.uploadFile 一次只能带一个文件，第二张眼底图通过
    formData 以 base64 传入，这里统一转回 UploadFile 供下游服务复用。
    """
    raw = b64.split(",", 1)[1] if "," in b64 else b64
    try:
        data = base64.b64decode(raw)
    except (binascii.Error, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"{filename} 图片数据无效"
        )
    return StarletteUploadFile(
        file=BytesIO(data),
        filename=filename,
        headers=Headers({"content-type": "image/png"}),
    )


@router.post(
    "/ma",
    summary="MA 微动脉瘤检测（单张眼底图）",
    response_model=None,
    dependencies=[write_dep],
)
async def diag_ma(
    db: DbSession,
    current_user: CurrentUser,
    file: UploadFile = File(..., description="眼底图（支持 PNG/JPG/TIFF/WEBP）"),
    eye: str = Form("UK", description="OD/OS/OU；UK 或空则按影像自动判断"),
    model_id: Optional[int] = Form(None, description="可选：CSU-EYES 模型 ID"),
):
    data = await DiagnosisService.ma_detection(
        db=db, user=current_user, file=file, eye=eye, model_id=model_id,
    )
    return success(
        data=data.model_dump(by_alias=True),
        msg=f"MA 检测完成：检出 {data.ma.ma_count if data.ma else 0} 个微动脉瘤",
    )


@router.post(
    "/dr",
    summary="DR 双眼分级（左右眼各一张）",
    response_model=None,
    dependencies=[write_dep],
)
async def diag_dr(
    db: DbSession,
    current_user: CurrentUser,
    left_eye: Optional[UploadFile] = File(None, description="左眼眼底图（OS）"),
    right_eye: Optional[UploadFile] = File(None, description="右眼眼底图（OD）"),
    left_eye_b64: Optional[str] = Form(None, description="左眼 base64（小程序端用）"),
    right_eye_b64: Optional[str] = Form(None, description="右眼 base64（小程序端用）"),
    model_id: Optional[int] = Form(None),
):
    # 兼容两种来源：multipart 文件（Web 端）或 base64 表单（微信小程序端）
    left = left_eye or (_b64_to_upload(left_eye_b64, "left_eye.png") if left_eye_b64 else None)
    right = right_eye or (_b64_to_upload(right_eye_b64, "right_eye.png") if right_eye_b64 else None)
    if left is None or right is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="DR 分级需要左右眼各一张眼底图",
        )
    data = await DiagnosisService.dr_grading(
        db=db, user=current_user, left_eye=left, right_eye=right, model_id=model_id,
    )
    return success(
        data=data.model_dump(by_alias=True),
        msg=f"DR 分级完成：综合 {data.dr.overall_grade if data.dr else 0} 级",
    )


@router.post(
    "/comprehensive",
    summary="综合诊断（单张眼底图，多任务）",
    response_model=None,
    dependencies=[write_dep],
)
async def diag_comp(
    db: DbSession,
    current_user: CurrentUser,
    file: UploadFile = File(..., description="眼底图（任意眼别）"),
    tasks: Optional[List[str]] = Form(None, description="任务清单：ma_detection / dr_grading"),
):
    data = await DiagnosisService.comprehensive(
        db=db, user=current_user, file=file, tasks=tasks,
    )
    return success(
        data=data.model_dump(by_alias=True),
        msg=f"综合诊断完成：DR {data.comprehensive.overall_grade if data.comprehensive else 0} 级 / "
            f"MA {data.comprehensive.ma_count if data.comprehensive else 0} 个",
    )
