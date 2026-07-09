"""
病例影像（一对多）路由
- GET    /case-images?caseTable=&caseId=          列出某病例所有影像（角色过滤可在前端做，或加 roles 参数）
- POST   /case-images/upload                       上传 / 补传（multipart）
- DELETE /case-images/{imageId}                    删除
- GET    /case-images/incomplete?caseTable=&...    列出影像不完整病例（管理员专用）
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, Path, Query, UploadFile

from app.common.response import success
from app.core.dependencies import CurrentUser, DbSession, require_roles
from app.db.models.user import RoleEnum
from app.schemas.case_image import IncompletePage
from app.services.case_image_service import CaseImageService

router = APIRouter(
    prefix="/case-images",
    tags=["11. 病例影像（一对多）"],
    dependencies=[Depends(require_roles(
        RoleEnum.STUDENT, RoleEnum.TEACHER, RoleEnum.ADMIN,
    ))],
)

write_dep = Depends(require_roles(RoleEnum.TEACHER, RoleEnum.ADMIN))
admin_dep = Depends(require_roles(RoleEnum.ADMIN))


@router.get(
    "",
    summary="按病例列出全部影像（按 role 分组）",
    response_model=None,
)
def list_case_images(
    current_user: CurrentUser,
    db: DbSession,
    caseTable: str = Query(..., description="screening / training"),
    caseId: int = Query(..., ge=1),
    roles: Optional[str] = Query(
        None,
        description="逗号分隔的 role 过滤；省略则返回全部",
    ),
):
    roles_list = [r.strip() for r in roles.split(",") if r.strip()] if roles else None
    data = CaseImageService.grouped(
        db, case_table=caseTable, case_id=caseId, roles_filter=roles_list,
    )
    return success(data=data.model_dump(by_alias=True))


@router.post(
    "/upload",
    summary="病例补传 / 追加影像（医生 / 管理员）",
    response_model=None,
    dependencies=[write_dep],
)
async def upload_case_image(
    current_user: CurrentUser,
    db: DbSession,
    caseTable: str = Form(...),
    caseId: int = Form(..., ge=1),
    role: str = Form(..., description="original/MA/HE/EX/SE/OD/color_mask/overlay/class_mask/other"),
    eye: str = Form("OU"),
    files: List[UploadFile] = File(...),
):
    saved = []
    for f in files:
        rec = await CaseImageService.add_upload(
            db, user=current_user,
            case_table=caseTable, case_id=caseId,
            file=f, role=role, eye=eye,
        )
        saved.append({
            "id": rec.id,
            "fileUrl": rec.file_url,
            "role": rec.role,
            "eye": rec.eye,
        })
    return success(data={"items": saved}, msg="已上传")


@router.delete(
    "/{imageId}",
    summary="删除某张影像（医生 / 管理员）",
    response_model=None,
    dependencies=[write_dep],
)
def delete_case_image(
    current_user: CurrentUser,
    db: DbSession,
    imageId: int = Path(..., ge=1),
):
    CaseImageService.delete(db, image_id=imageId, user=current_user)
    return success(msg="已删除")


@router.get(
    "/incomplete",
    summary="列出影像不完整的病例（管理员）",
    response_model=None,
    dependencies=[admin_dep],
)
def list_incomplete(
    current_user: CurrentUser,
    db: DbSession,
    caseTable: str = Query("training", description="screening / training"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=200),
):
    total, rows = CaseImageService.list_incomplete(
        db, case_table=caseTable, page=page, page_size=pageSize,
    )
    data = IncompletePage(
        total=total, page=page, page_size=pageSize, list=rows,
    )
    return success(data=data.model_dump(by_alias=True))
