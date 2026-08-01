"""
实训培训路由
- 与前端 frontend/src/api/training.ts 完全对齐
- 统一 { code, msg, data } 响应包
- 角色：STUDENT / TEACHER / ADMIN

接口清单（对齐 OpenAPI Training 标签）：
    GET  /training/cases                        病例分页列表
    GET  /training/cases/{caseId}               病例详情
    GET  /training/cases/{caseId}/heatmap       AI 热力图
    GET  /training/cases/{caseId}/gold          金标准标注
    GET  /training/cases/{caseId}/iou-history   历史 IoU
    PUT  /training/cases/{caseId}/done          标记完成
    POST /training/annotations/submit           提交标注（入库 + IoU）
    POST /training/iou/calculate                试算 IoU（不入库）
    GET  /training/stats                        个人培训统计
    GET  /training/cases/{caseId}/ai-diagnosis  AI 辅助诊断（读缓存）
    POST /training/cases/{caseId}/ai-diagnosis  AI 辅助诊断（执行推理）
    POST /training/ai-cases                     AI 智能建案（教师/管理员）
"""

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Path, Query, UploadFile

from app.common.response import success
from app.core.dependencies import CurrentUser, DbSession, require_roles
from app.db.models.user import RoleEnum
from app.schemas.training import (
    CaseListQuery,
    SubmitAnnotationParams,
)
from app.services.training_service import TrainingService
from app.services.training_ai_service import TrainingAiService

router = APIRouter(
    prefix="/training",
    tags=["3. 实训培训"],
    dependencies=[Depends(require_roles(RoleEnum.STUDENT, RoleEnum.TEACHER, RoleEnum.ADMIN))],
)


# ====================== 1. 病例列表 ======================

@router.get(
    "/cases",
    summary="获取病例分页列表",
    description="按关键词 / DR 分级 / 难度 / 完成状态过滤，分页返回",
    response_model=None,
)
def list_cases(
    current_user: CurrentUser,
    db: DbSession,
    keyword: Optional[str] = Query(None, description="关键词（编号/标题/描述）"),
    drLevel: Optional[int] = Query(None, ge=0, le=4, description="DR 分级 0~4"),
    difficulty: Optional[str] = Query(None, description="难度：入门/初级/中级/高级"),
    done: Optional[bool] = Query(None, description="是否已完成"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(100, ge=1, le=500),
):
    query = CaseListQuery(
        keyword=keyword,
        dr_level=drLevel,  # type: ignore[arg-type]
        difficulty=difficulty,  # type: ignore[arg-type]
        done=done,
        page=page,
        page_size=pageSize,
    )
    data = TrainingService.list_cases(db=db, user=current_user, query=query)
    return success(data=data.model_dump(by_alias=True))


# ====================== 2. 病例详情 ======================

@router.get(
    "/cases/{caseId}",
    summary="获取病例详情",
    response_model=None,
)
def get_case(
    current_user: CurrentUser,
    db: DbSession,
    caseId: str = Path(..., description="病例编号 CASE001"),
):
    data = TrainingService.get_case(db=db, user=current_user, case_id=caseId)
    return success(data=data.model_dump(by_alias=True))


# ====================== 3. 热力图 ======================

@router.get(
    "/cases/{caseId}/heatmap",
    summary="获取 AI 热力图（GradCAM）",
    response_model=None,
)
def get_heatmap(
    current_user: CurrentUser,
    db: DbSession,
    caseId: str = Path(...),
):
    data = TrainingService.get_heatmap(db=db, case_id=caseId)
    return success(data=data.model_dump(by_alias=True))


# ====================== 4. 金标准 ======================

@router.get(
    "/cases/{caseId}/gold",
    summary="获取金标准标注",
    response_model=None,
)
def get_gold(
    current_user: CurrentUser,
    db: DbSession,
    caseId: str = Path(...),
):
    data = TrainingService.get_gold(db=db, case_id=caseId, user=current_user)
    return success(data=data.model_dump(by_alias=True))


# ====================== 5. 历史 IoU ======================

@router.get(
    "/cases/{caseId}/iou-history",
    summary="获取病例历史 IoU 评分",
    response_model=None,
)
def iou_history(
    current_user: CurrentUser,
    db: DbSession,
    caseId: str = Path(...),
):
    data = TrainingService.iou_history(db=db, user=current_user, case_id=caseId)
    return success(data=[d.model_dump(by_alias=True) for d in data])


# ====================== 6. 标记完成 ======================

@router.put(
    "/cases/{caseId}/done",
    summary="标记病例为已完成",
    response_model=None,
)
def mark_done(
    current_user: CurrentUser,
    db: DbSession,
    caseId: str = Path(...),
):
    TrainingService.mark_case_done(db=db, user=current_user, case_id=caseId)
    return success(msg="已标记为完成")


# ====================== 7. 提交标注（入库） ======================

@router.post(
    "/annotations/submit",
    summary="提交标注并计算 IoU（结果入库）",
    response_model=None,
)
def submit_annotation(
    params: SubmitAnnotationParams,
    current_user: CurrentUser,
    db: DbSession,
):
    data = TrainingService.submit_annotation(
        db=db, user=current_user, params=params, persist=True,
    )
    return success(data=data.model_dump(by_alias=True), msg="提交成功")


# ====================== 8. 试算 IoU ======================

@router.post(
    "/iou/calculate",
    summary="试算 IoU（不入库）",
    response_model=None,
)
def calculate_iou(
    params: SubmitAnnotationParams,
    current_user: CurrentUser,
    db: DbSession,
):
    data = TrainingService.submit_annotation(
        db=db, user=current_user, params=params, persist=False,
    )
    return success(data=data.model_dump(by_alias=True))


# ====================== 9. AI 辅助诊断（真实算法服务） ======================

@router.get(
    "/cases/{caseId}/ai-diagnosis",
    summary="获取 AI 辅助诊断结果（仅读缓存，不触发推理）",
    response_model=None,
)
def get_ai_diagnosis(
    current_user: CurrentUser,
    db: DbSession,
    caseId: str = Path(..., description="病例编号 case_no 或数字 ID"),
):
    data = TrainingAiService.get_cached(db=db, case_id=caseId)
    return success(data=data.model_dump(by_alias=True) if data else None)


@router.post(
    "/cases/{caseId}/ai-diagnosis",
    summary="执行 AI 辅助诊断（调用 CSU-EYES 算法服务，结果缓存）",
    response_model=None,
)
async def run_ai_diagnosis(
    current_user: CurrentUser,
    db: DbSession,
    caseId: str = Path(..., description="病例编号 case_no 或数字 ID"),
    force: bool = Query(False, description="True 时忽略缓存重新推理"),
):
    data = await TrainingAiService.diagnose(db=db, case_id=caseId, force=force)
    return success(
        data=data.model_dump(by_alias=True),
        msg="命中缓存" if data.cached else f"AI 诊断完成：{data.overall_label or ('综合 DR ' + str(data.overall_grade) + ' 级')}",
    )


# ====================== 10. AI 智能建案（教师/管理员） ======================

@router.post(
    "/ai-cases",
    summary="AI 智能建案：上传左右眼底图，自动分级生成实训病例草稿",
    response_model=None,
    dependencies=[Depends(require_roles(RoleEnum.TEACHER, RoleEnum.ADMIN))],
)
async def create_ai_case(
    current_user: CurrentUser,
    db: DbSession,
    left_eye: UploadFile = File(..., description="左眼眼底图（OS）"),
    right_eye: UploadFile = File(..., description="右眼眼底图（OD）"),
    title: str = Form("", description="病例标题（缺省自动生成）"),
    difficulty: str = Form("EASY", description="难度 EASY/MEDIUM/HARD"),
):
    data = await TrainingAiService.create_ai_case(
        db=db, user=current_user,
        left_eye=left_eye, right_eye=right_eye,
        title=title, difficulty=difficulty,
    )
    return success(
        data=data.model_dump(by_alias=True),
        msg=f"建案成功：{data.case_id}（AI 综合 DR {data.ai.overall_grade} 级，草稿待复核）",
    )


# ====================== 11. 个人培训统计 ======================

@router.get(
    "/stats",
    summary="获取个人培训统计",
    response_model=None,
)
def stats(
    current_user: CurrentUser,
    db: DbSession,
):
    data = TrainingService.stats(db=db, user=current_user)
    return success(data=data.model_dump(by_alias=True))
