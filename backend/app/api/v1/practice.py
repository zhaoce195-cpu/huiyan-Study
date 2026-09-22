"""
学员自主练习路由
- 与前端 frontend/src/api/practice.ts 对齐
- 角色：STUDENT / TEACHER / ADMIN 均可访问，权限在 service 细化
- 接口清单：
    GET    /practice/random              随机抽取病例
    GET    /practice/cases/{caseId}      指定病例摘要
    GET    /practice/cases/{caseId}/gold 金标准（提交后才可看）
    POST   /practice/start               开始练习（创建/复用 DRAFT）
    POST   /practice/submit              提交并自动评分
    GET    /practice/list                练习台账（学员只看自己）
    GET    /practice/{recordId}          练习详情
    POST   /practice/{recordId}/review   教师点评
    DELETE /practice/{recordId}          删除（自己 DRAFT 或 ADMIN）
    GET    /practice/stats/me            个人统计
    GET    /practice/stats/user/{userId} 指定学员统计（TEACHER/ADMIN）
    GET    /practice/stats/all           全班级统计（TEACHER/ADMIN）
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Path, Query

from app.common.response import success
from app.core.dependencies import CurrentUser, DbSession, require_roles
from app.db.models.user import RoleEnum
from app.schemas.practice import (
    PracticeListQuery,
    PracticeRandomQuery,
    PracticeReviewParams,
    PracticeStartParams,
    PracticeSubmitParams,
    TextQuizPaperOut,
    TextQuizQuestionOut,
    TextQuizResultOut,
    TextQuizSubmitIn,
)
from app.services.practice_service import PracticeService
from app.services.text_quiz import draw_paper, submit_paper

router = APIRouter(
    prefix="/practice",
    tags=["8. 自主练习"],
    dependencies=[Depends(require_roles(RoleEnum.STUDENT, RoleEnum.TEACHER, RoleEnum.ADMIN))],
)


# ---------- 病例抽取 ----------

@router.get("/random", summary="随机抽取一份病例", response_model=None)
def random_case(
    current_user: CurrentUser,
    db: DbSession,
    category: Optional[str] = Query(None),
    difficulty: Optional[str] = Query(None),
    drLevel: Optional[int] = Query(None, ge=0, le=4),
    excludeDone: bool = Query(True, description="排除已通过的病例"),
):
    query = PracticeRandomQuery(
        category=category,
        difficulty=difficulty,
        dr_level=drLevel,
        exclude_done=excludeDone,
    )
    data = PracticeService.random_case(db=db, user=current_user, query=query)
    return success(data=data.model_dump(by_alias=True))


@router.get("/cases/{caseId}", summary="指定病例练习摘要", response_model=None)
def case_brief(
    current_user: CurrentUser,
    db: DbSession,
    caseId: int = Path(..., ge=1),
):
    data = PracticeService.case_brief(db=db, user=current_user, case_id=caseId)
    return success(data=data.model_dump(by_alias=True))


@router.get(
    "/cases/{caseId}/gold",
    summary="获取病例金标准（学员需先提交才可查看）",
    response_model=None,
)
def get_gold(
    current_user: CurrentUser,
    db: DbSession,
    caseId: int = Path(..., ge=1),
):
    data = PracticeService.get_gold_standard(db=db, user=current_user, case_id=caseId)
    return success(data=data.model_dump(by_alias=True))


# ---------- 练习 ----------

@router.post("/start", summary="开始练习（创建或复用 DRAFT）", response_model=None)
def start_practice(
    params: PracticeStartParams,
    current_user: CurrentUser,
    db: DbSession,
):
    data = PracticeService.start(db=db, user=current_user, params=params)
    return success(data=data.model_dump(by_alias=True))


@router.post("/exam/start", summary="开始或继续正式考试", response_model=None)
def start_exam(current_user: CurrentUser, db: DbSession):
    data = PracticeService.start_exam(db=db, user=current_user)
    return success(data=data.model_dump(by_alias=True))


@router.post("/submit", summary="提交练习（自动评分）", response_model=None)
def submit_practice(
    params: PracticeSubmitParams,
    current_user: CurrentUser,
    db: DbSession,
):
    data = PracticeService.submit(db=db, user=current_user, params=params)
    return success(data=data.model_dump(by_alias=True), msg="提交成功")


# ---------- 文字题（知识点 / 选择 / 填空）----------

@router.get("/text-quiz", summary="抽一组文字题", response_model=None)
def text_quiz_paper(size: int = Query(4, ge=3, le=8)):
    paper = TextQuizPaperOut(questions=[TextQuizQuestionOut(**row) for row in draw_paper(size)])
    return success(data=paper.model_dump(by_alias=True))


@router.post("/text-quiz", summary="提交一组文字题", response_model=None)
def text_quiz_submit(
    params: TextQuizSubmitIn,
    current_user: CurrentUser,
    db: DbSession,
):
    result = submit_paper(
        db, current_user, [(row.id, row.value) for row in params.answers],
    )
    out = TextQuizResultOut(**result)
    return success(data=out.model_dump(by_alias=True), msg="已判分")


# ---------- 台账 ----------

@router.get("/list", summary="练习台账分页", response_model=None)
def list_records(
    current_user: CurrentUser,
    db: DbSession,
    userId: Optional[int] = Query(None, ge=1),
    caseId: Optional[int] = Query(None, ge=1),
    status: Optional[str] = Query(None, description="DRAFT/SUBMITTED/REVIEWED"),
    isPassed: Optional[bool] = Query(None),
    startTime: Optional[datetime] = Query(None),
    endTime: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=200),
):
    query = PracticeListQuery(
        user_id=userId,
        case_id=caseId,
        status=status,  # type: ignore[arg-type]
        is_passed=isPassed,
        start_time=startTime,
        end_time=endTime,
        page=page,
        page_size=pageSize,
    )
    data = PracticeService.list_records(db=db, user=current_user, query=query)
    return success(data=data.model_dump(by_alias=True))


@router.get("/{recordId}", summary="练习记录详情（含评分细节）", response_model=None)
def get_detail(
    current_user: CurrentUser,
    db: DbSession,
    recordId: int = Path(..., ge=1),
):
    data = PracticeService.get_detail(db=db, user=current_user, record_id=recordId)
    return success(data=data.model_dump(by_alias=True))


@router.post(
    "/{recordId}/review",
    summary="教师对学员练习进行点评（TEACHER/ADMIN）",
    response_model=None,
)
def review_record(
    params: PracticeReviewParams,
    current_user: CurrentUser,
    db: DbSession,
    recordId: int = Path(..., ge=1),
):
    data = PracticeService.review(
        db=db, user=current_user, record_id=recordId, params=params,
    )
    return success(data=data.model_dump(by_alias=True), msg="已点评")


@router.post("/{recordId}/hint", summary="平时练习打开下一则提示", response_model=None)
def next_hint(
    current_user: CurrentUser,
    db: DbSession,
    recordId: int = Path(..., ge=1),
):
    data = PracticeService.next_hint(db=db, user=current_user, record_id=recordId)
    return success(data=data.model_dump(by_alias=True))


@router.delete("/{recordId}", summary="删除练习记录（自己 DRAFT 或 ADMIN）", response_model=None)
def delete_record(
    current_user: CurrentUser,
    db: DbSession,
    recordId: int = Path(..., ge=1),
):
    PracticeService.delete(db=db, user=current_user, record_id=recordId)
    return success(msg="已删除")


# ---------- 统计 ----------

@router.get("/stats/me", summary="个人练习统计", response_model=None)
def stats_me(current_user: CurrentUser, db: DbSession):
    data = PracticeService.stats(db=db, user=current_user, target_user_id=None)
    return success(data=data.model_dump(by_alias=True))


@router.get(
    "/stats/user/{userId}",
    summary="指定学员练习统计（TEACHER/ADMIN）",
    response_model=None,
)
def stats_user(
    current_user: CurrentUser,
    db: DbSession,
    userId: int = Path(..., ge=1),
):
    data = PracticeService.stats(db=db, user=current_user, target_user_id=userId)
    return success(data=data.model_dump(by_alias=True))


@router.get(
    "/stats/all",
    summary="全班级练习统计（TEACHER/ADMIN）",
    response_model=None,
)
def stats_all(current_user: CurrentUser, db: DbSession):
    data = PracticeService.stats(db=db, user=current_user, target_user_id=0)
    return success(data=data.model_dump(by_alias=True))
