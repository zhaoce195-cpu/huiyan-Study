"""
体检端别名路由 —— 与体检业务流程贴合的命名空间。

本模块仅提供更贴近业务命名的入口，实际逻辑全部委托给
`screening_service.ScreeningService` —— 不重复实现，不破坏既有接口。

接口清单：
    POST /physical/confirm-report   医生确认体检报告 + 推送至病患账号
"""

from fastapi import APIRouter, Depends

from app.common.response import success
from app.core.dependencies import CurrentUser, DbSession, require_roles
from app.db.models.user import RoleEnum
from app.schemas.screening import ConfirmReportParams
from app.services.screening_service import ScreeningService

router = APIRouter(
    prefix="/physical",
    tags=["4-1. 体检端报告确认"],
    dependencies=[Depends(require_roles(RoleEnum.TEACHER, RoleEnum.ADMIN))],
)


@router.post(
    "/confirm-report",
    summary="医生确认报告并推送至病患账号（生成 PDF + 写入 confirmed 状态）",
    response_model=None,
)
def confirm_report(
    params: ConfirmReportParams,
    current_user: CurrentUser,
    db: DbSession,
):
    """
    业务侧建议入口（与 /screening/reports/confirm 等价）。

    成功后：
    - 病例 status=REVIEWED，report_status=confirmed
    - 按 patient_phone 绑定 patient_user_id（命中时）
    - 生成体检报告 PDF 并落盘，路径写入 report_pdf_path
    """
    data = ScreeningService.confirm_report(
        db=db, params=params, user=current_user,
    )
    bound_msg = "已推送至病患账号" if data.patient_bound else "暂未匹配到病患账号，待病患注册后即可查看"
    return success(
        data=data.model_dump(by_alias=True),
        msg=f"报告已确认，{bound_msg}",
    )
