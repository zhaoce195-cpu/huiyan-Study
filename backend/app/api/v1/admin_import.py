"""
管理员批量导入路由
- POST /admin/import/idrid
"""

from fastapi import APIRouter, Depends

from app.common.response import success
from app.core.dependencies import CurrentUser, DbSession, require_roles
from app.db.models.user import RoleEnum
from app.schemas.case_image import IdridImportParams
from app.services.idrid_import_service import run_idrid_import

router = APIRouter(
    prefix="/admin/import",
    tags=["12. 管理员批量导入"],
    dependencies=[Depends(require_roles(RoleEnum.ADMIN))],
)


@router.post(
    "/idrid",
    summary="批量导入 IDRiD 数据集（管理员）",
    response_model=None,
)
def import_idrid(
    params: IdridImportParams,
    current_user: CurrentUser,
    db: DbSession,
):
    data = run_idrid_import(
        db,
        source_path=params.source_path,
        limit=params.limit,
        dry_run=params.dry_run,
        skip_existing=params.skip_existing,
        creator=current_user,
    )
    msg = (
        f"模拟运行完成，未写入数据库" if params.dry_run
        else f"已导入 {data.imported_cases} 条病例，关联 {data.appended_images} 张影像"
    )
    return success(data=data.model_dump(by_alias=True), msg=msg)
