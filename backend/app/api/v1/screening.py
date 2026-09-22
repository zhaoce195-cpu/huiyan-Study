"""
AI 筛查模块路由
- 与前端 frontend/src/api/screening.ts 完全对齐
- 统一 { code, msg, data } 响应包；导出文件接口走二进制流
- 权限：仅 TEACHER（带教医师）/ ADMIN 可上传 / 删除 / 重新分析 / 转诊
       STUDENT 可读列表与统计，不能写入

接口清单（共 12 个，对齐 OpenAPI Screening 标签）：
    POST   /screening/upload                    单张眼底图上传 + AI 分析
    POST   /screening/upload/batch              批量上传
    GET    /screening/tasks                     任务分页列表
    GET    /screening/tasks/export              列表 Excel        【先于 /tasks/{taskId}】
    POST   /screening/tasks/reanalyze           重新分析
    GET    /screening/tasks/{taskId}            任务详情
    DELETE /screening/tasks/{taskId}            移除任务
    GET    /screening/stats                     风险/状态统计
    GET    /screening/reports/summary/pdf       汇总报告 PDF      【先于 /reports/{taskId}】
    GET    /screening/reports/{taskId}          报告详情
    GET    /screening/reports/{taskId}/pdf      单份报告 PDF
    POST   /screening/refer                     高危一键转诊
"""

from datetime import datetime
from typing import List, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Path, Query, UploadFile
from fastapi.responses import Response

from app.common.response import success
from app.core.dependencies import CurrentUser, DbSession, require_roles
from app.db.models.user import RoleEnum
from app.schemas.screening import (
    BatchTaskIdsParams,
    BatchTaskOpResult,
    CaseImageDeleteParams,
    CaseUpdateParams,
    ConfirmReportParams,
    PatientMetaForm,
    ReanalyzeParams,
    ReferParams,
)
from app.services.screening_export import (
    render_single_report_pdf,
    render_summary_pdf,
    render_tasks_excel,
)
from app.services.screening_service import ScreeningService


# 读权限（三角色均可）
read_dep = Depends(require_roles(RoleEnum.STUDENT, RoleEnum.TEACHER, RoleEnum.ADMIN))
# 写权限（仅医师 / 管理员）
write_dep = Depends(require_roles(RoleEnum.TEACHER, RoleEnum.ADMIN))


router = APIRouter(
    prefix="/screening",
    tags=["4. AI 筛查"],
    dependencies=[read_dep],
)


# ============== 工具：附件文件名 Header ==============

def _attach_filename_header(filename: str) -> dict:
    """RFC5987 兼容的 Content-Disposition，避免中文文件名乱码"""
    quoted = quote(filename, safe="")
    return {
        "Content-Disposition": f"attachment; filename=\"download\"; filename*=UTF-8''{quoted}",
        "Cache-Control": "no-store",
    }


# ============================================================
#                   上传相关
# ============================================================

@router.post(
    "/upload",
    summary="单张眼底图上传 + AI 分析",
    description="支持 JPG/PNG/BMP/WEBP，最大 20MB；上传后立即同步执行 AI 推理",
    response_model=None,
    dependencies=[write_dep],
)
async def upload_fundus(
    current_user: CurrentUser,
    db: DbSession,
    file: UploadFile = File(..., description="眼底图文件"),
    patientId: Optional[str] = Form(None),
    patientName: Optional[str] = Form(None),
    gender: Optional[str] = Form(None),
    age: Optional[int] = Form(None),
    eye: Optional[str] = Form(None),
    hospital: Optional[str] = Form(None),
    doctor: Optional[str] = Form(None),
    remark: Optional[str] = Form(None),
):
    meta = PatientMetaForm(
        patient_id=patientId,
        patient_name=patientName,
        gender=gender,  # type: ignore[arg-type]
        age=age,
        eye=eye,  # type: ignore[arg-type]
        hospital=hospital,
        doctor=doctor,
        remark=remark,
    )
    data = await ScreeningService.upload_single(db=db, user=current_user, file=file, meta=meta)
    return success(data=data.model_dump(by_alias=True), msg="上传成功")


@router.post(
    "/upload/batch",
    summary="批量上传眼底图",
    response_model=None,
    dependencies=[write_dep],
)
async def upload_fundus_batch(
    current_user: CurrentUser,
    db: DbSession,
    files: List[UploadFile] = File(..., description="多张眼底图"),
    hospital: Optional[str] = Form(None),
    doctor: Optional[str] = Form(None),
):
    meta = PatientMetaForm(hospital=hospital, doctor=doctor)
    data = await ScreeningService.upload_batch(db=db, user=current_user, files=files, meta=meta)
    return success(data=data.model_dump(by_alias=True), msg="批量上传完成")


# ============================================================
#                   任务（列表 / 详情 / 删除 / 导出）
#
#   ⚠ FastAPI 按声明顺序匹配：
#   /tasks/export 与 /tasks/reanalyze 必须在 /tasks/{taskId} 之前声明
# ============================================================

@router.get(
    "/tasks",
    summary="获取筛查任务分页列表",
    response_model=None,
)
def list_tasks(
    current_user: CurrentUser,
    db: DbSession,
    keyword: Optional[str] = Query(None),
    risk: Optional[str] = Query(None, description="red/yellow/green"),
    status: Optional[str] = Query(None, description="queued/analyzing/done/failed"),
    startTime: Optional[str] = Query(None),
    endTime: Optional[str] = Query(None),
    hospital: Optional[str] = Query(None),
    caseNo: Optional[str] = Query(None, description="病例编号模糊搜索"),
    patientName: Optional[str] = Query(None, description="患者姓名模糊搜索"),
    phone: Optional[str] = Query(None, description="手机号模糊搜索"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(50, ge=1, le=500),
    sortBy: str = Query("createdAt"),
    sortOrder: str = Query("desc"),
    scope: Optional[str] = Query(
        None,
        description=(
            "queue=仅排队中/处理中/失败（分析任务队列视图）；"
            "archive=仅已完成/已复核（病例检索视图）；"
            "省略则返回全部，向下兼容"
        ),
    ),
    diagnosisType: Optional[str] = Query(None, description="MA / DR / COMPREHENSIVE 过滤"),
):
    # STUDENT 仅可看自己提交的；TEACHER/ADMIN 看全部
    only_user = (
        current_user.id
        if (current_user.role and current_user.role.code == RoleEnum.STUDENT.value)
        else None
    )
    data = ScreeningService.list_tasks(
        db=db,
        keyword=keyword,
        risk=risk,
        status_filter=status,
        start_time=startTime,
        end_time=endTime,
        hospital=hospital,
        case_no=caseNo,
        patient_name=patientName,
        phone=phone,
        page=page,
        page_size=pageSize,
        sort_by=sortBy,
        sort_order=sortOrder,
        only_user_id=only_user,
        scope=scope,
        diagnosis_type=diagnosisType,
    )
    return success(data=data.model_dump(by_alias=True))


@router.get(
    "/tasks/export",
    summary="导出筛查任务 Excel",
    description="按当前筛选条件导出，最多 2000 条",
    response_model=None,
)
def export_excel(
    current_user: CurrentUser,
    db: DbSession,
    keyword: Optional[str] = Query(None),
    risk: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    startTime: Optional[str] = Query(None),
    endTime: Optional[str] = Query(None),
    hospital: Optional[str] = Query(None),
    caseNo: Optional[str] = Query(None),
    patientName: Optional[str] = Query(None),
    phone: Optional[str] = Query(None),
):
    page_data = ScreeningService.list_tasks(
        db=db,
        keyword=keyword,
        risk=risk,
        status_filter=status,
        start_time=startTime,
        end_time=endTime,
        hospital=hospital,
        case_no=caseNo,
        patient_name=patientName,
        phone=phone,
        page=1,
        page_size=2000,
    )
    xlsx_bytes = render_tasks_excel(page_data.list)
    filename = f"screening_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=_attach_filename_header(filename),
    )


@router.post(
    "/tasks/reanalyze",
    summary="重新分析任务",
    response_model=None,
    dependencies=[write_dep],
)
def reanalyze(
    params: ReanalyzeParams,
    current_user: CurrentUser,
    db: DbSession,
):
    data = ScreeningService.reanalyze(db=db, params=params)
    return success(data=data.model_dump(by_alias=True), msg="已重新加入分析队列")


@router.post(
    "/tasks/batch-delete",
    summary="批量删除筛查任务（病例 / 队列通用）",
    response_model=None,
    dependencies=[write_dep],
)
def batch_delete(
    params: BatchTaskIdsParams,
    current_user: CurrentUser,
    db: DbSession,
):
    data = ScreeningService.batch_delete_tasks(db=db, task_ids=params.task_ids)
    return success(
        data=BatchTaskOpResult(**data).model_dump(by_alias=True),
        msg=f"已批量移除 {data['success_count']} 条",
    )


@router.post(
    "/tasks/batch-remove-queue",
    summary="批量从分析任务队列移出（仅排队中 / 处理中 / 失败）",
    response_model=None,
    dependencies=[write_dep],
)
def batch_remove_queue(
    params: BatchTaskIdsParams,
    current_user: CurrentUser,
    db: DbSession,
):
    data = ScreeningService.batch_remove_from_queue(db=db, task_ids=params.task_ids)
    return success(
        data=BatchTaskOpResult(**data).model_dump(by_alias=True),
        msg=(
            f"已从队列移出 {data['success_count']} 条"
            + (f"；{data['skipped_count']} 条非队列任务已跳过" if data['skipped_count'] else "")
        ),
    )


@router.get(
    "/tasks/{taskId}",
    summary="获取单个筛查任务详情",
    response_model=None,
)
def get_task(
    current_user: CurrentUser,
    db: DbSession,
    taskId: str = Path(...),
):
    data = ScreeningService.get_task(db=db, task_id=taskId)
    return success(data=data.model_dump(by_alias=True))


@router.delete(
    "/tasks/{taskId}",
    summary="移除筛查任务",
    response_model=None,
    dependencies=[write_dep],
)
def delete_task(
    current_user: CurrentUser,
    db: DbSession,
    taskId: str = Path(...),
):
    ScreeningService.delete_task(db=db, task_id=taskId)
    return success(msg="已移除")


# ============================================================
#                   统计
# ============================================================

@router.get(
    "/stats",
    summary="获取风险/状态统计",
    response_model=None,
)
def stats(
    current_user: CurrentUser,
    db: DbSession,
    scope: Optional[str] = Query(
        None,
        description="queue=仅队列中任务；archive=仅已完成；省略=全部",
    ),
):
    data = ScreeningService.stats(db=db, scope=scope)
    return success(data=data.model_dump(by_alias=True))


# ============================================================
#                   报告（详情 / 单份 PDF / 汇总 PDF）
#
#   ⚠ /reports/summary/pdf 必须先于 /reports/{taskId} 声明
# ============================================================

@router.get(
    "/reports/summary/pdf",
    summary="导出汇总报告 PDF（按筛选条件）",
    response_model=None,
)
def export_summary_pdf(
    current_user: CurrentUser,
    db: DbSession,
    keyword: Optional[str] = Query(None),
    risk: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    startTime: Optional[str] = Query(None),
    endTime: Optional[str] = Query(None),
    hospital: Optional[str] = Query(None),
    caseNo: Optional[str] = Query(None),
    patientName: Optional[str] = Query(None),
    phone: Optional[str] = Query(None),
):
    page_data = ScreeningService.list_tasks(
        db=db,
        keyword=keyword,
        risk=risk,
        status_filter=status,
        start_time=startTime,
        end_time=endTime,
        hospital=hospital,
        case_no=caseNo,
        patient_name=patientName,
        phone=phone,
        page=1,
        page_size=500,
    )
    pdf_bytes = render_summary_pdf(page_data.list)
    filename = f"screening_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers=_attach_filename_header(filename),
    )


@router.get(
    "/reports/{taskId}/pdf",
    summary="导出单份筛查报告 PDF",
    response_model=None,
)
def export_single_pdf(
    current_user: CurrentUser,
    db: DbSession,
    taskId: str = Path(...),
):
    report = ScreeningService.get_report(db=db, task_id=taskId)
    pdf_bytes = render_single_report_pdf(report)
    filename = f"{report.report_no or taskId}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers=_attach_filename_header(filename),
    )


@router.get(
    "/reports/{taskId}",
    summary="获取筛查报告详情",
    response_model=None,
)
def get_report(
    current_user: CurrentUser,
    db: DbSession,
    taskId: str = Path(...),
):
    data = ScreeningService.get_report(db=db, task_id=taskId)
    return success(data=data.model_dump(by_alias=True))


# ============================================================
#                   转诊
# ============================================================

@router.post(
    "/refer",
    summary="高危病例一键转诊",
    response_model=None,
    dependencies=[write_dep],
)
def refer_high_risk(
    params: ReferParams,
    current_user: CurrentUser,
    db: DbSession,
):
    ScreeningService.refer(db=db, params=params, user=current_user)
    return success(msg="转诊申请已提交")


# ============================================================
#                   报告确认（医生 → 同步病患账号）
# ============================================================

@router.post(
    "/reports/confirm",
    summary="医生确认报告（推进至 REVIEWED + 自动同步至病患账号）",
    response_model=None,
    dependencies=[write_dep],
)
def confirm_report(
    params: ConfirmReportParams,
    current_user: CurrentUser,
    db: DbSession,
):
    data = ScreeningService.confirm_report(
        db=db, params=params, user=current_user,
    )
    return success(
        data=data.model_dump(by_alias=True),
        msg="报告已确认" + ("，已同步至病患账号" if data.patient_bound else "（暂未匹配到病患账号）"),
    )


# ============================================================
#         病例补充修改（医生 / 管理员补充修改 + 上传眼底图）
# ============================================================

@router.put(
    "/cases/{caseId}",
    summary="补充 / 修改病例信息（医生、管理员）",
    description=(
        "可修改字段：患者姓名 / 性别 / 年龄 / 联系电话 / 主诉 / 病史 / 备注。\n"
        "patient_phone 同步写入 phone 与 patient_phone（用于病患账号绑定）。"
    ),
    response_model=None,
    dependencies=[write_dep],
)
def update_case(
    params: CaseUpdateParams,
    current_user: CurrentUser,
    db: DbSession,
    caseId: int = Path(..., ge=1),
):
    data = ScreeningService.update_case(
        db=db, user=current_user, case_id=caseId, params=params,
    )
    return success(data=data.model_dump(by_alias=True), msg="已保存")


@router.get(
    "/cases/{caseId}/images",
    summary="病例眼底图列表",
    response_model=None,
)
def list_case_images(
    current_user: CurrentUser,
    db: DbSession,
    caseId: int = Path(..., ge=1),
):
    data = ScreeningService.list_case_images(db=db, case_id=caseId)
    return success(data=data.model_dump(by_alias=True))


@router.post(
    "/cases/{caseId}/images",
    summary="病例补充上传眼底图（医生、管理员）",
    description="支持 PNG/JPG/JPEG/WEBP/BMP，单文件最大 20MB；支持多文件",
    response_model=None,
    dependencies=[write_dep],
)
async def add_case_images(
    current_user: CurrentUser,
    db: DbSession,
    caseId: int = Path(..., ge=1),
    files: List[UploadFile] = File(..., description="眼底图文件（可多张）"),
    eye: str = Form("UK", description="眼别 OD/OS/OU；UK 或空则按影像自动判断"),
):
    data = await ScreeningService.add_case_images(
        db=db, user=current_user, case_id=caseId, files=files, eye=eye,
    )
    return success(data=data.model_dump(by_alias=True), msg="影像已补充")


@router.delete(
    "/cases/{caseId}/images",
    summary="删除病例的某张眼底图（医生、管理员）",
    response_model=None,
    dependencies=[write_dep],
)
def delete_case_image(
    params: CaseImageDeleteParams,
    current_user: CurrentUser,
    db: DbSession,
    caseId: int = Path(..., ge=1),
):
    data = ScreeningService.delete_case_image(
        db=db, user=current_user, case_id=caseId, image_url=params.url,
    )
    return success(data=data.model_dump(by_alias=True), msg="已删除")
