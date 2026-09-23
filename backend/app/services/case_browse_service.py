"""
病例浏览检索业务层
- 多条件筛选 + 分页
- 角色权限：
    STUDENT 仅看 is_published=True 且 archive_status=ACTIVE 的病例
    TEACHER 看自己创建的全部 + 其他教师已发布的（不含其他教师未发布草稿）
    ADMIN   看全部，含已归档
- 病例详情 + 归档（更新 archive_status）
"""

from datetime import datetime
import re
from typing import List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from app.db.models import (
    CaseArchiveStatusEnum,
    CaseCategoryEnum,
    CaseDifficultyEnum,
    RoleEnum,
    RotationTask,
    RotationTaskAck,
    RotationTaskKindEnum,
    TrainingCase,
    User,
)
from app.common.dr_grade import grade_level, grade_text
from app.common.diagnosis_form import fundus_only as case_is_fundus_only
from app.core.content_policy import PresentationMode, Scene, redact, resolve_mode
from app.schemas.case_browse import (
    CaseArchiveParams,
    CaseBrowseDetail,
    CaseBrowseItem,
    CaseBrowseQuery,
    CaseBrowsePage,
    CaseVisitBrief,
    GoldStandardUpdate,
    SubjectLinkUpdate,
)


CATEGORY_TEXT = {
    CaseCategoryEnum.DR.value: "糖尿病视网膜病变",
    CaseCategoryEnum.AMD.value: "老年性黄斑变性",
    CaseCategoryEnum.GLAUCOMA.value: "青光眼",
    CaseCategoryEnum.HYPERTENSION.value: "高血压性视网膜病变",
    CaseCategoryEnum.NORMAL.value: "正常眼底",
    CaseCategoryEnum.OTHER.value: "其他",
}

DIFFICULTY_TEXT = {
    CaseDifficultyEnum.EASY.value: "入门",
    CaseDifficultyEnum.MEDIUM.value: "中级",
    CaseDifficultyEnum.HARD.value: "高级",
}

DR_GRADE_TEXT = {
    "0": "0 级 无 DR",
    "1": "1 级 轻度 NPDR",
    "2": "2 级 中度 NPDR",
    "3": "3 级 重度 NPDR",
    "4": "4 级 PDR（增殖性）",
}


def _flatten_images(image_paths: Optional[dict]) -> List[str]:
    """已迁移到 app.common.case_utils.flatten_image_paths（保留旧名以兼容本文件其他引用）"""
    from app.common.case_utils import flatten_image_paths
    return flatten_image_paths(image_paths)


def _first_image(image_paths: Optional[dict]) -> Optional[str]:
    images = _flatten_images(image_paths)
    return images[0] if images else None


def _answered_case_ids(
    db: Session, user: Optional[User], case_ids: List[int],
) -> set:
    """
    返回该用户在给定病例中「已提交作答」的病例 ID 集合。

    盲态解除的唯一依据：必须由服务端查询作答记录得出，
    不接受前端传入的任何标记。教师 / 管理员不受盲态约束，直接返回全集。
    """
    if not case_ids or user is None:
        return set()

    role_code = user.role.code if user.role else None
    if role_code in (RoleEnum.TEACHER.value, RoleEnum.ADMIN.value):
        return set(case_ids)

    # 延迟导入，避免与 practice 模块循环引用
    from app.db.models.practice_session import PracticeSession, PracticeStatusEnum

    rows = (
        db.query(PracticeSession.case_id)
        .filter(
            PracticeSession.user_id == user.id,
            PracticeSession.case_id.in_(case_ids),
            PracticeSession.status.in_([
                PracticeStatusEnum.SUBMITTED.value,
                PracticeStatusEnum.REVIEWED.value,
            ]),
        )
        .all()
    )
    return {row[0] for row in rows}


def _blind_mode_for(viewer: Optional[User], answered: bool) -> PresentationMode:
    """病例浏览场景的呈现模式（服务端推导，不接受前端指定）"""
    return resolve_mode(
        viewer_role=viewer.role.code if (viewer and viewer.role) else None,
        scene=Scene.CASE_BROWSE,
        answered=answered,
    )


def _exam_order(case: TrainingCase):
    text = (getattr(case, "exam_on", "") or "").strip()
    return (0 if text else 1, text, case.id)


def _series(db: Session, user: User, subject_nos: set) -> dict:
    """同一教学编号下、当前角色能看见的检查，按日期从早到晚。没写日期的排在后面。"""
    subjects = {(item or "").strip() for item in subject_nos if (item or "").strip()}
    if not subjects:
        return {}
    rows = (
        _scope_query(db, user)
        .filter(TrainingCase.subject_no.in_(subjects))
        .all()
    )
    grouped: dict = {}
    for row in rows:
        grouped.setdefault((row.subject_no or "").strip(), []).append(row)
    for group in grouped.values():
        group.sort(key=_exam_order)
    return grouped


def visit_context(db: Session, user: User, case: TrainingCase) -> dict:
    """阅片、练习和病例库共用这一份时期关系。改病人编号或检查日期后，各处看到的是同一次检查。"""
    index, count, visits = _visit_pair(
        _series(db, user, {getattr(case, "subject_no", "") or ""}),
        case,
    )
    exam_on = (getattr(case, "exam_on", "") or "").strip()
    exam_date = None
    if exam_on:
        try:
            exam_date = datetime.strptime(exam_on, "%Y-%m-%d")
        except ValueError:
            exam_on = ""
    return {
        "subject_no": (getattr(case, "subject_no", "") or "").strip(),
        "exam_on": exam_on,
        "exam_date": exam_date,
        "visit_index": index,
        "visit_count": count,
        "visits": visits,
    }


def _visit_pair(series: dict, case: TrainingCase):
    subject = (getattr(case, "subject_no", "") or "").strip()
    group = series.get(subject) or []
    if len(group) < 2:
        return 1, 1, []
    index = next((i for i, row in enumerate(group, start=1) if row.id == case.id), 1)
    visits = [
        CaseVisitBrief(
            id=row.id,
            case_no=row.case_no,
            exam_on=(getattr(row, "exam_on", "") or "").strip(),
            visit_index=i,
        )
        for i, row in enumerate(group, start=1)
        if row.id != case.id
    ]
    return index, len(group), visits


def _clean_exam_on(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="检查日期请写成 2024-03-01。没有日期就留空，不要编造",
        )
    return text


_SUBJECT_PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_SUBJECT_IDCARD = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")


def _clean_subject_no(value: str) -> str:
    text = (value or "").strip()[:32]
    if _SUBJECT_PHONE.search(text) or _SUBJECT_IDCARD.search(text):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="病人编号不要填手机号或身份证号",
        )
    return text


def _to_item(
    case: TrainingCase,
    *,
    comp: Optional[dict] = None,
    image_count: Optional[int] = None,
    viewer: Optional[User] = None,
    answered: bool = False,
    derived_count: int = 0,
    visit_index: int = 1,
    visit_count: int = 1,
) -> CaseBrowseItem:
    from app.common.case_utils import learner_patient_fields, mask_phone_by_role

    creator_name = ""
    creator_role = ""
    if case.creator is not None:
        creator_name = case.creator.real_name or case.creator.username
        creator_role = case.creator.role.code if case.creator.role else ""

    images = _flatten_images(case.image_paths)
    # 空值表示「DR 分级不适用」，不得回落成 '0'（报告 P1）
    dr_raw = case.gold_dr_grade

    image_complete = True
    missing_roles: List[str] = []
    if comp is not None:
        image_complete = bool(comp.get("complete", True))
        missing_roles = list(comp.get("missing_roles", []) or [])

    # ============ 角色脱敏 ============
    viewer_role = viewer.role.code if (viewer and viewer.role) else None
    phone_out, phone_visible = mask_phone_by_role(
        getattr(case, "patient_phone", "") or "",
        viewer_role,
    )
    patient_name, patient_gender, patient_age = learner_patient_fields(
        viewer_role,
        getattr(case, "patient_name", "") or "",
        case.patient_gender or "U",
        case.patient_age,
    )

    item = CaseBrowseItem(
        id=case.id,
        case_no=case.case_no,
        case_sn=getattr(case, "case_sn", "") or "",
        title=case.title or "",
        description=case.description or "",
        category=case.category,  # type: ignore[arg-type]
        category_text=CATEGORY_TEXT.get(case.category, ""),
        difficulty=case.difficulty,
        difficulty_text=DIFFICULTY_TEXT.get(case.difficulty, ""),
        dr_level=grade_level(dr_raw),
        dr_grade_text=grade_text(dr_raw),
        archive_status=case.archive_status,  # type: ignore[arg-type]
        is_published=bool(case.is_published),
        is_train_case=bool(getattr(case, "is_train_case", False)),
        creator_id=case.creator_id,
        creator_name=creator_name,
        creator_role=creator_role,
        thumb_url=_first_image(case.image_paths),
        image_count=image_count if image_count is not None else len(images),
        image_complete=image_complete,
        fundus_only=case_is_fundus_only(case),
        derived_count=derived_count,
        missing_roles=missing_roles,
        patient_name=patient_name,
        patient_gender=patient_gender,
        patient_age=patient_age,
        patient_phone=phone_out,
        phone_visible=phone_visible,
        subject_no=(getattr(case, "subject_no", "") or "").strip(),
        exam_on=(getattr(case, "exam_on", "") or "").strip(),
        visit_index=visit_index,
        visit_count=visit_count,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )

    # ============ 盲训内容策略：作答前不下发答案型字段 ============
    mode = _blind_mode_for(viewer, answered)
    return CaseBrowseItem(**redact(item.model_dump(), mode, case_no=case.case_no))


def _to_detail(
    case: TrainingCase,
    *,
    comp: Optional[dict] = None,
    image_count: Optional[int] = None,
    viewer: Optional[User] = None,
    answered: bool = False,
    db: Optional[Session] = None,
) -> CaseBrowseDetail:
    visit_index, visit_count, visits = 1, 1, []
    if db is not None and viewer is not None:
        visit_index, visit_count, visits = _visit_pair(
            _series(db, viewer, {getattr(case, "subject_no", "") or ""}),
            case,
        )
    base = _to_item(
        case, comp=comp, image_count=image_count, viewer=viewer, answered=answered,
        visit_index=visit_index, visit_count=visit_count,
    )
    clinical = case.clinical_info or ""
    stored_name = (getattr(case, "patient_name", "") or "").strip()
    role_code = viewer.role.code if (viewer and viewer.role) else None
    from app.common.case_utils import teaching_staff
    if stored_name and not teaching_staff(role_code):
        clinical = clinical.replace(stored_name, case.case_no)
    if case_is_fundus_only(case) and not teaching_staff(role_code):
        clinical = ""
    detail = CaseBrowseDetail(
        **base.model_dump(),
        clinical_info=clinical,
        image_paths=case.image_paths or {},
        images=_flatten_images(case.image_paths),
        gold_dr_grade=case.gold_dr_grade if case.gold_dr_grade is not None else "",
        gold_diagnosis=case.gold_diagnosis or "",
        teaching_points=case.teaching_points or "",
        gold_lesions=list(case.gold_lesions or []),
        pass_score=case.pass_score or 60,
        visits=visits,
    )
    # base 已裁剪，此处再裁剪一次以覆盖 detail 独有的答案字段
    # （gold_diagnosis / teaching_points）
    mode = _blind_mode_for(viewer, answered)
    return CaseBrowseDetail(**redact(detail.model_dump(), mode, case_no=case.case_no))


def _scope_query(db: Session, user: User):
    """根据角色返回基础 query（包含权限过滤）"""
    role_code = user.role.code if user.role else None
    q = db.query(TrainingCase)

    if role_code == RoleEnum.ADMIN.value:
        return q

    if role_code == RoleEnum.TEACHER.value:
        # 教师：自己创建的 + 其他教师已发布的（不看草稿）
        return q.filter(
            or_(
                TrainingCase.creator_id == user.id,
                TrainingCase.is_published == True,  # noqa: E712
            )
        )

    # 学员：仅已发布 + ACTIVE
    return q.filter(
        TrainingCase.is_published == True,  # noqa: E712
        TrainingCase.archive_status == CaseArchiveStatusEnum.ACTIVE.value,
    )


class CaseBrowseService:

    @staticmethod
    def list_cases(db: Session, user: User, query: CaseBrowseQuery) -> CaseBrowsePage:
        from app.db.models import CaseImage
        from app.services.case_image_service import CaseImageService
        from sqlalchemy import func

        q = _scope_query(db, user)

        if query.keyword:
            kw = f"%{query.keyword.strip()}%"
            clauses = [
                TrainingCase.case_no.like(kw),
                TrainingCase.case_sn.like(kw),
                TrainingCase.title.like(kw),
                TrainingCase.description.like(kw),
                User.real_name.like(kw),
                User.username.like(kw),
            ]
            # 学员检索不能靠姓名或手机号把人找出来
            role_code = user.role.code if user.role else None
            from app.common.case_utils import teaching_staff
            if teaching_staff(role_code):
                clauses.extend([
                    TrainingCase.patient_name.like(kw),
                    TrainingCase.patient_phone.like(kw),
                ])
            q = q.outerjoin(User, User.id == TrainingCase.creator_id).filter(or_(*clauses))

        if query.category:
            q = q.filter(TrainingCase.category == query.category)

        if query.dr_level is not None:
            q = q.filter(TrainingCase.gold_dr_grade == str(query.dr_level))

        if query.difficulty:
            q = q.filter(TrainingCase.difficulty == query.difficulty)

        if query.archive_status:
            q = q.filter(TrainingCase.archive_status == query.archive_status)

        if query.creator_role:
            from app.db.models.role import Role
            q = q.join(User, User.id == TrainingCase.creator_id).join(
                Role, Role.id == User.role_id
            ).filter(Role.code == query.creator_role)

        if query.start_time:
            q = q.filter(TrainingCase.created_at >= query.start_time)
        if query.end_time:
            q = q.filter(TrainingCase.created_at <= query.end_time)

        total = q.count()
        rows: List[TrainingCase] = (
            q.order_by(desc(TrainingCase.id))
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
            .all()
        )

        # 批量取每条病例的影像数 + 完整性，避免 N+1 后再循环查
        ids = [c.id for c in rows]
        count_map: dict = {}
        derived_map: dict = {}
        if ids:
            # 只统计原始影像。此前把 mask / overlay / 金标准一起计入，
            # 列表因此显示「8 张影像」却说不清哪些是原图——
            # 正是报告 P1 抱怨的场景。派生对象另行计数。
            count_rows = (
                db.query(CaseImage.case_id, func.count(CaseImage.id))
                .filter(
                    CaseImage.case_table == "training",
                    CaseImage.case_id.in_(ids),
                    CaseImage.role == "original",
                )
                .group_by(CaseImage.case_id)
                .all()
            )
            count_map = {cid: cnt for cid, cnt in count_rows}

            derived_rows = (
                db.query(CaseImage.case_id, func.count(CaseImage.id))
                .filter(
                    CaseImage.case_table == "training",
                    CaseImage.case_id.in_(ids),
                    CaseImage.role != "original",
                )
                .group_by(CaseImage.case_id)
                .all()
            )
            derived_map = {cid: cnt for cid, cnt in derived_rows}

        # 批量取本人已提交作答的病例，用于解除盲态（一次查询，避免 N+1）
        answered_ids = _answered_case_ids(db, user, ids)
        series = _series(db, user, {(c.subject_no or "") for c in rows})

        items: List[CaseBrowseItem] = []
        for c in rows:
            comp = CaseImageService.case_completeness(
                db, case_table="training", case_id=c.id,
            )
            ic = count_map.get(c.id, 0) or len(_flatten_images(c.image_paths))
            visit_index, visit_count, _visits = _visit_pair(series, c)
            items.append(_to_item(
                c, comp=comp, image_count=ic, viewer=user,
                answered=c.id in answered_ids,
                derived_count=derived_map.get(c.id, 0),
                visit_index=visit_index,
                visit_count=visit_count,
            ))

        if query.only_incomplete:
            items = [it for it in items if not it.image_complete]
            total = len(items)

        return CaseBrowsePage(
            total=total,
            page=query.page,
            page_size=query.page_size,
            list=items,
        )

    @staticmethod
    def get_detail(db: Session, user: User, case_id: int) -> CaseBrowseDetail:
        case = db.query(TrainingCase).filter(TrainingCase.id == case_id).first()
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"病例不存在：{case_id}",
            )

        # 学员：未发布或已归档不可见
        role_code = user.role.code if user.role else None
        if role_code == RoleEnum.STUDENT.value:
            if (
                not case.is_published
                or case.archive_status == CaseArchiveStatusEnum.ARCHIVED.value
            ):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="病例不存在或当前不可访问",
                )

        return _to_detail(
            case,
            viewer=user,
            db=db,
            answered=bool(_answered_case_ids(db, user, [case.id])),
        )

    @staticmethod
    def archive(
        db: Session,
        user: User,
        case_id: int,
        params: CaseArchiveParams,
    ) -> CaseBrowseDetail:
        role_code = user.role.code if user.role else None
        if role_code not in (RoleEnum.TEACHER.value, RoleEnum.ADMIN.value):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无归档权限",
            )

        case = db.query(TrainingCase).filter(TrainingCase.id == case_id).first()
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"病例不存在：{case_id}",
            )

        # 教师只能归档自己创建的
        if (
            role_code == RoleEnum.TEACHER.value
            and case.creator_id != user.id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="仅可归档本人创建的病例",
            )

        case.archive_status = params.archive_status
        case.updated_at = datetime.now()
        db.commit()
        db.refresh(case)
        return _to_detail(case, viewer=user, db=db)

    @staticmethod
    def set_subject(
        db: Session,
        user: User,
        case_id: int,
        params: SubjectLinkUpdate,
    ) -> CaseBrowseDetail:
        role_code = user.role.code if user.role else None
        if role_code not in (RoleEnum.TEACHER.value, RoleEnum.ADMIN.value):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="只有教师可以关联同一病人的检查",
            )
        case = db.query(TrainingCase).filter(TrainingCase.id == case_id).first()
        if not case:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="病例不存在")
        if role_code == RoleEnum.TEACHER.value and case.creator_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="只能修改本人创建的病例",
            )
        case.subject_no = _clean_subject_no(params.subject_no)
        case.exam_on = _clean_exam_on(params.exam_on)
        db.commit()
        return CaseBrowseService.get_detail(db, user, case.id)

    # ============================================================
    #                   加入实训
    # ============================================================

    @staticmethod
    def join_training(
        db: Session,
        user: User,
        case_id: int,
    ) -> CaseBrowseDetail:
        """
        将一个病例加入实训库（学员端方可见 / 可练习）。

        权限：仅 TEACHER / ADMIN 可调用。
        幂等：已是 is_train_case=True 的病例不报错，原样返回。
        归档病例：禁止加入。
        """
        role_code = user.role.code if user.role else None
        if role_code not in (RoleEnum.TEACHER.value, RoleEnum.ADMIN.value):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="仅教师或管理员可执行加入实训操作",
            )

        case = db.query(TrainingCase).filter(TrainingCase.id == case_id).first()
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"病例不存在：{case_id}",
            )
        if case.archive_status == CaseArchiveStatusEnum.ARCHIVED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该病例已归档，无法加入实训",
            )

        if not case.is_train_case:
            case.is_train_case = True
            # 默认同步置为已发布，确保学员实际可见（可视具体业务调整）
            if not case.is_published:
                case.is_published = True
            case.updated_at = datetime.now()
            db.commit()
            db.refresh(case)

        return _to_detail(case, viewer=user, db=db)

    @staticmethod
    def remove_from_training(
        db: Session,
        user: User,
        case_id: int,
    ) -> CaseBrowseDetail:
        """从实训库移除（撤销）。仅 TEACHER / ADMIN 可调用。"""
        role_code = user.role.code if user.role else None
        if role_code not in (RoleEnum.TEACHER.value, RoleEnum.ADMIN.value):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="仅教师或管理员可移除实训病例",
            )

        case = db.query(TrainingCase).filter(TrainingCase.id == case_id).first()
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"病例不存在：{case_id}",
            )

        case.is_train_case = False
        case.updated_at = datetime.now()
        task_ids = [
            row[0]
            for row in db.query(RotationTask.id)
            .filter(
                RotationTask.kind == RotationTaskKindEnum.CASE.value,
                RotationTask.case_id == case.id,
            )
            .all()
        ]
        if task_ids:
            db.query(RotationTaskAck).filter(RotationTaskAck.task_id.in_(task_ids)).delete(
                synchronize_session=False
            )
            db.query(RotationTask).filter(RotationTask.id.in_(task_ids)).delete(
                synchronize_session=False
            )
        db.commit()
        db.refresh(case)
        return _to_detail(case, viewer=user, db=db)

    # ============================================================
    #                   金标准修订 / 发布
    # ============================================================

    @staticmethod
    def update_gold_standard(
        db: Session,
        user: User,
        case_id: int,
        params: GoldStandardUpdate,
    ) -> CaseBrowseDetail:
        """
        教师修订金标准。

        publish=False：仅写金标准字段，保持未发布，学员不可见。
        publish=True：写金标准后同时置 is_published + is_train_case，
        学员抽题 / 阅片即可看到。
        """
        role_code = user.role.code if user.role else None
        if role_code not in (RoleEnum.TEACHER.value, RoleEnum.ADMIN.value):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="仅教师或管理员可修订金标准",
            )

        case = db.query(TrainingCase).filter(TrainingCase.id == case_id).first()
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"病例不存在：{case_id}",
            )
        if (
            role_code == RoleEnum.TEACHER.value
            and case.creator_id != user.id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="仅可修订本人创建的病例金标准",
            )
        if case.archive_status == CaseArchiveStatusEnum.ARCHIVED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="已归档病例不可修订金标准",
            )

        if params.gold_dr_grade is not None:
            grade = (params.gold_dr_grade or "").strip()
            if grade and grade not in DR_GRADE_TEXT:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="金标准 DR 分级只能是 0~4，或留空表示不适用",
                )
            case.gold_dr_grade = grade
        if params.gold_diagnosis is not None:
            case.gold_diagnosis = params.gold_diagnosis.strip()
        if params.teaching_points is not None:
            case.teaching_points = params.teaching_points.strip()
        if params.pass_score is not None:
            case.pass_score = params.pass_score
        if params.gold_lesions is not None:
            case.gold_lesions = params.gold_lesions

        if params.publish:
            if not (case.gold_diagnosis or "").strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="发布前请填写金标准诊断",
                )
            case.is_published = True
            case.is_train_case = True

        case.updated_at = datetime.now()
        db.commit()
        db.refresh(case)
        return _to_detail(case, viewer=user, db=db)
