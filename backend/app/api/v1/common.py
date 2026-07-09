"""
公共模块路由
- 与前端 frontend/src/api/common.ts 完全对齐
- 统一 { code, msg, data } 响应包

接口清单（共 21 个）：
    系统/健康
        GET    /common/system/config            系统配置（公开）
        GET    /common/ping                     健康检查（公开）
        GET    /common/time                     服务器当前时间

    字典
        GET    /common/dict/{type}              单类字典
        POST   /common/dict/batch               批量获取多类字典

    医院 / 科室
        GET    /common/hospitals                医院列表
        GET    /common/departments              科室列表（带分页/管理用）
        POST   /common/departments              新建科室            (ADMIN)
        PUT    /common/departments/{id}         更新科室            (ADMIN)
        DELETE /common/departments/{id}         删除科室            (ADMIN)

    通知
        GET    /common/notifications            我的通知列表
        POST   /common/notifications/read       标记已读
        POST   /common/notifications/read-all   全部标记已读

    公告管理（后台）
        GET    /common/notices                  公告分页（管理）   (TEACHER/ADMIN)
        GET    /common/notices/{id}             公告详情
        POST   /common/notices                  新建公告           (TEACHER/ADMIN)
        PUT    /common/notices/{id}             更新公告           (TEACHER/ADMIN)
        DELETE /common/notices/{id}             删除公告           (ADMIN)

    文件上传
        POST   /common/upload                   通用单文件上传

    日志
        GET    /common/logs/operation           操作日志查询      (ADMIN)

    平台统计
        GET    /common/stats/training           全院培训统计      (TEACHER/ADMIN)
        GET    /common/stats/study-hours        学员学时汇总      (TEACHER/ADMIN)
"""

from datetime import datetime
from typing import Optional
from urllib.parse import urljoin

from fastapi import APIRouter, Depends, File, Form, Path, Query, Request, UploadFile

from app.common.response import success
from app.common.utils import save_common_upload
from app.core.dependencies import (
    CurrentUser,
    DbSession,
    get_current_user,
    require_roles,
)
from app.db.models.user import RoleEnum
from app.schemas.common import (
    DepartmentSaveParams,
    DictBatchParams,
    NoticeSaveParams,
    NotificationReadParams,
    PingOut,
    ServerTimeOut,
    UploadFileResultOut,
)
from app.services.common_service import CommonService
from app.services.notice_service import NoticeService
from app.services.op_log_service import OpLogService

# 角色门控
admin_only = Depends(require_roles(RoleEnum.ADMIN))
teacher_admin = Depends(require_roles(RoleEnum.TEACHER, RoleEnum.ADMIN))
any_login = Depends(get_current_user)

router = APIRouter(prefix="/common", tags=["5. 公共模块"])


# ============================================================
#                   系统配置 / 健康 / 时间（公开）
# ============================================================

@router.get(
    "/system/config",
    summary="获取系统配置",
    description="公开接口，无需登录",
    response_model=None,
)
def system_config():
    data = CommonService.system_config()
    return success(data=data.model_dump(by_alias=True))


@router.get(
    "/ping",
    summary="服务健康检查",
    description="公开接口，无需登录",
    response_model=None,
)
def ping():
    data = PingOut(status="ok", time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    return success(data=data.model_dump(by_alias=True))


@router.get(
    "/time",
    summary="获取服务器当前时间",
    response_model=None,
    dependencies=[any_login],
)
def server_time():
    data = ServerTimeOut(
        time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        timezone="Asia/Shanghai",
    )
    return success(data=data.model_dump(by_alias=True))


# ============================================================
#                   字典
# ============================================================

@router.get(
    "/dict/batch",
    summary="批量获取字典（GET 兜底）",
    description="支持通过 ?types=a,b,c 形式批量取，与 POST 等价",
    response_model=None,
    dependencies=[any_login],
    include_in_schema=False,
)
def dict_batch_get(types: str = Query("", description="逗号分隔多个 dict 类型")):
    type_list = [t.strip() for t in types.split(",") if t.strip()]
    out = CommonService.dict_batch(type_list)
    return success(data={k: [it.model_dump(by_alias=True) for it in v] for k, v in out.items()})


@router.post(
    "/dict/batch",
    summary="批量获取字典",
    response_model=None,
    dependencies=[any_login],
)
def dict_batch(params: DictBatchParams):
    out = CommonService.dict_batch(params.types)
    return success(data={k: [it.model_dump(by_alias=True) for it in v] for k, v in out.items()})


@router.get(
    "/dict/{type}",
    summary="根据字典类型获取字典",
    response_model=None,
    dependencies=[any_login],
)
def dict_one(type: str = Path(..., description="字典类型 dr_level/lesion_type 等")):
    items = CommonService.dict_by_type(type)
    return success(data=[it.model_dump(by_alias=True) for it in items])


# ============================================================
#                   医院 / 科室
# ============================================================

@router.get(
    "/hospitals",
    summary="获取医院列表",
    response_model=None,
    dependencies=[any_login],
)
def hospitals(keyword: Optional[str] = Query(None)):
    items = CommonService.hospitals(keyword)
    return success(data=[h.model_dump(by_alias=True) for h in items])


@router.get(
    "/departments",
    summary="获取科室列表",
    response_model=None,
    dependencies=[any_login],
)
def departments(
    db: DbSession,
    hospitalId: Optional[int] = Query(None),
):
    items = CommonService.list_departments(db=db, hospital_id=hospitalId)
    return success(data=[d.model_dump(by_alias=True) for d in items])


@router.post(
    "/departments",
    summary="新建科室",
    response_model=None,
    dependencies=[admin_only],
)
def create_department(
    params: DepartmentSaveParams,
    current_user: CurrentUser,
    db: DbSession,
    request: Request,
):
    data = CommonService.create_department(db=db, params=params)
    OpLogService.record(
        db, user=current_user, module="common", action="dept.create",
        detail=f"新建科室 {data.name}",
        ip=request.client.host if request.client else "",
        commit=True,
    )
    return success(data=data.model_dump(by_alias=True), msg="创建成功")


@router.put(
    "/departments/{deptId}",
    summary="更新科室",
    response_model=None,
    dependencies=[admin_only],
)
def update_department(
    params: DepartmentSaveParams,
    current_user: CurrentUser,
    db: DbSession,
    request: Request,
    deptId: int = Path(...),
):
    data = CommonService.update_department(db=db, dept_id=deptId, params=params)
    OpLogService.record(
        db, user=current_user, module="common", action="dept.update",
        detail=f"更新科室 #{deptId} → {data.name}",
        ip=request.client.host if request.client else "",
    )
    return success(data=data.model_dump(by_alias=True), msg="更新成功")


@router.delete(
    "/departments/{deptId}",
    summary="删除科室",
    response_model=None,
    dependencies=[admin_only],
)
def delete_department(
    current_user: CurrentUser,
    db: DbSession,
    request: Request,
    deptId: int = Path(...),
):
    CommonService.delete_department(db=db, dept_id=deptId)
    OpLogService.record(
        db, user=current_user, module="common", action="dept.delete",
        detail=f"删除科室 #{deptId}",
        ip=request.client.host if request.client else "",
    )
    return success(msg="删除成功")


# ============================================================
#                   通知 / 公告
# ============================================================

@router.get(
    "/notifications",
    summary="获取我的通知",
    response_model=None,
    dependencies=[any_login],
)
def notifications(
    current_user: CurrentUser,
    db: DbSession,
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
):
    data = NoticeService.my_notifications(db=db, user=current_user, page=page, page_size=pageSize)
    return success(data=data.model_dump(by_alias=True))


@router.post(
    "/notifications/read",
    summary="标记通知已读",
    response_model=None,
    dependencies=[any_login],
)
def mark_read(
    params: NotificationReadParams,
    current_user: CurrentUser,
    db: DbSession,
):
    int_ids = []
    for x in params.ids:
        try:
            int_ids.append(int(x))
        except (TypeError, ValueError):
            continue
    NoticeService.mark_read(db=db, user=current_user, ids=int_ids)
    return success(msg="已标为已读")


@router.post(
    "/notifications/read-all",
    summary="全部标记已读",
    response_model=None,
    dependencies=[any_login],
)
def mark_all_read(current_user: CurrentUser, db: DbSession):
    NoticeService.mark_all_read(db=db, user=current_user)
    return success(msg="已全部标为已读")


# ----------- 公告管理（后台）-----------

@router.get(
    "/notices",
    summary="公告分页列表（管理）",
    response_model=None,
    dependencies=[teacher_admin],
)
def list_notices(
    current_user: CurrentUser,
    db: DbSession,
    keyword: Optional[str] = Query(None),
    noticeType: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
):
    data = NoticeService.list(
        db=db, keyword=keyword,
        notice_type=noticeType, status_filter=status,
        page=page, page_size=pageSize,
    )
    return success(data=data.model_dump(by_alias=True))


@router.get(
    "/notices/{noticeId}",
    summary="公告详情（自动 +1 阅读量）",
    response_model=None,
    dependencies=[any_login],
)
def detail_notice(
    current_user: CurrentUser,
    db: DbSession,
    noticeId: int = Path(...),
):
    data = NoticeService.detail(db=db, notice_id=noticeId)
    return success(data=data.model_dump(by_alias=True))


@router.post(
    "/notices",
    summary="新建公告",
    response_model=None,
    dependencies=[teacher_admin],
)
def create_notice(
    params: NoticeSaveParams,
    current_user: CurrentUser,
    db: DbSession,
    request: Request,
):
    data = NoticeService.create(db=db, user=current_user, params=params)
    OpLogService.record(
        db, user=current_user, module="common", action="notice.create",
        detail=f"新建公告 {data.title}",
        ip=request.client.host if request.client else "",
    )
    return success(data=data.model_dump(by_alias=True), msg="发布成功")


@router.put(
    "/notices/{noticeId}",
    summary="更新公告",
    response_model=None,
    dependencies=[teacher_admin],
)
def update_notice(
    params: NoticeSaveParams,
    current_user: CurrentUser,
    db: DbSession,
    request: Request,
    noticeId: int = Path(...),
):
    data = NoticeService.update(db=db, notice_id=noticeId, params=params)
    OpLogService.record(
        db, user=current_user, module="common", action="notice.update",
        detail=f"更新公告 #{noticeId}",
        ip=request.client.host if request.client else "",
    )
    return success(data=data.model_dump(by_alias=True), msg="更新成功")


@router.delete(
    "/notices/{noticeId}",
    summary="删除公告",
    response_model=None,
    dependencies=[admin_only],
)
def delete_notice(
    current_user: CurrentUser,
    db: DbSession,
    request: Request,
    noticeId: int = Path(...),
):
    NoticeService.delete(db=db, notice_id=noticeId)
    OpLogService.record(
        db, user=current_user, module="common", action="notice.delete",
        detail=f"删除公告 #{noticeId}",
        ip=request.client.host if request.client else "",
    )
    return success(msg="删除成功")


# ============================================================
#                   文件上传
# ============================================================

@router.post(
    "/upload",
    summary="通用单文件上传",
    description="支持图片/文档/压缩包，单文件最大 50MB；biz 字段决定存储子目录",
    response_model=None,
    dependencies=[any_login],
)
async def common_upload(
    current_user: CurrentUser,
    request: Request,
    file: UploadFile = File(..., description="待上传文件"),
    biz: Optional[str] = Form(None, description="业务标识，如 avatar/notice/report-attach"),
):
    rel_url, file_name, size_bytes, mime = await save_common_upload(
        file=file, biz=biz or "misc", user_id=current_user.id,
    )
    base = str(request.base_url).rstrip("/") if request.base_url else ""
    full_url = urljoin(base + "/", rel_url.lstrip("/"))
    data = UploadFileResultOut(
        url=rel_url,
        full_url=full_url,
        file_name=file_name,
        file_size=size_bytes,
        mime_type=mime,
    )
    return success(data=data.model_dump(by_alias=True), msg="上传成功")


# ============================================================
#                   日志
# ============================================================

@router.get(
    "/logs/operation",
    summary="操作日志查询",
    response_model=None,
    dependencies=[admin_only],
)
def list_op_logs(
    current_user: CurrentUser,
    db: DbSession,
    module: Optional[str] = Query(None),
    startTime: Optional[str] = Query(None),
    endTime: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=200),
):
    data = OpLogService.list(
        db=db, module=module,
        start_time=startTime, end_time=endTime,
        page=page, page_size=pageSize,
    )
    return success(data=data.model_dump(by_alias=True))


# ============================================================
#                   平台统计
# ============================================================

@router.get(
    "/stats/training",
    summary="全院培训统计",
    description="覆盖学员/病例/答卷/合格率/难度分布/DR 分级分布",
    response_model=None,
    dependencies=[teacher_admin],
)
def stats_training(
    current_user: CurrentUser,
    db: DbSession,
):
    data = CommonService.training_overview(db=db)
    return success(data=data.model_dump(by_alias=True))


@router.get(
    "/stats/study-hours",
    summary="学员学时汇总",
    description="按学员维度汇总作答总时长 / 病例数 / 平均 IoU",
    response_model=None,
    dependencies=[teacher_admin],
)
def stats_study_hours(
    current_user: CurrentUser,
    db: DbSession,
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    pageSize: int = Query(50, ge=1, le=200),
):
    data = CommonService.study_hours(db=db, keyword=keyword, page=page, page_size=pageSize)
    return success(data=data.model_dump(by_alias=True))
