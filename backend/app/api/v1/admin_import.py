"""
管理员批量导入路由
- POST /admin/import/idrid            批量导入 IDRiD 数据集
- POST /admin/import/backfill-patient 补齐教学病例的模拟患者信息
"""

from fastapi import APIRouter, Depends

from app.common.response import success
from app.core.dependencies import CurrentUser, DbSession, require_roles
from app.db.models.user import RoleEnum
from app.schemas.case_image import BackfillPatientParams, IdridImportParams
from app.services.backfill_patient_service import backfill_patient_info
from app.services.idrid_import_service import run_idrid_import
from app.services.op_log_service import OpLogService

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


@router.post(
    "/backfill-patient",
    summary="补齐教学病例的模拟患者信息（管理员）",
    response_model=None,
)
def backfill_patient(
    params: BackfillPatientParams,
    current_user: CurrentUser,
    db: DbSession,
):
    """
    训练病例来自公开数据集，本就没有患者身份，教学场景需要一个称呼
    与基本人口学信息。生成是确定性的：同一病例号永远得到同一组值，
    重跑不会让数据来回变，也不会让已进 PACS 的 DICOM 与业务库对不上。

    筛查病例对应真实受检者，一律不生成也不覆盖。
    """
    data = backfill_patient_info(
        db,
        only_empty=params.only_empty,
        overwrite=params.overwrite,
    )
    OpLogService.record(
        db, user=current_user, module="admin", action="backfill_patient",
        detail=(
            f"补齐模拟患者信息 {data.training_filled}/{data.training_total} 例"
            f"（{'覆盖' if params.overwrite else '仅补空'}），"
            f"流水号 {data.case_sn_filled} 条"
        ),
    )
    return success(
        data=data.model_dump(by_alias=True),
        msg=f"已补齐 {data.training_filled} 例教学病例，"
            f"流水号 {data.case_sn_filled} 条",
    )
