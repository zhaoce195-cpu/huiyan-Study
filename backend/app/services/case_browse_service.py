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
from typing import List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from app.db.models import (
    CaseArchiveStatusEnum,
    CaseCategoryEnum,
    CaseDifficultyEnum,
    RoleEnum,
    TrainingCase,
    User,
)
from app.common.dr_grade import grade_level, grade_text
from app.core.content_policy import PresentationMode, Scene, redact, resolve_mode
from app.schemas.case_browse import (
    CaseArchiveParams,
    CaseBrowseDetail,
    CaseBrowseItem,
    CaseBrowseQuery,
    CaseBrowsePage,
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


def _to_item(
    case: TrainingCase,
    *,
    comp: Optional[dict] = None,
    image_count: Optional[int] = None,
    viewer: Optional[User] = None,
    answered: bool = False,
    derived_count: int = 0,
) -> CaseBrowseItem:
    from app.common.case_utils import mask_phone_by_role

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
        derived_count=derived_count,
        missing_roles=missing_roles,
        patient_name=getattr(case, "patient_name", "") or "",
        patient_gender=case.patient_gender or "U",
        patient_age=case.patient_age or 0,
        patient_phone=phone_out,
        phone_visible=phone_visible,
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
) -> CaseBrowseDetail:
    base = _to_item(
        case, comp=comp, image_count=image_count, viewer=viewer, answered=answered,
    )
    detail = CaseBrowseDetail(
        **base.model_dump(),
        clinical_info=case.clinical_info or "",
        image_paths=case.image_paths or {},
        images=_flatten_images(case.image_paths),
        gold_diagnosis=case.gold_diagnosis or "",
        teaching_points=case.teaching_points or "",
        pass_score=case.pass_score or 60,
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
            q = q.outerjoin(User, User.id == TrainingCase.creator_id).filter(
                or_(
                    TrainingCase.case_no.like(kw),
                    TrainingCase.case_sn.like(kw),
                    TrainingCase.title.like(kw),
                    TrainingCase.description.like(kw),
                    TrainingCase.patient_name.like(kw),
                    TrainingCase.patient_phone.like(kw),
                    User.real_name.like(kw),
                    User.username.like(kw),
                )
            )

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

        items: List[CaseBrowseItem] = []
        for c in rows:
            comp = CaseImageService.case_completeness(
                db, case_table="training", case_id=c.id,
            )
            ic = count_map.get(c.id, 0) or len(_flatten_images(c.image_paths))
            items.append(_to_item(
                c, comp=comp, image_count=ic, viewer=user,
                answered=c.id in answered_ids,
                derived_count=derived_map.get(c.id, 0),
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
        return _to_detail(case, viewer=user)

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

        return _to_detail(case, viewer=user)

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

        if case.is_train_case:
            case.is_train_case = False
            case.updated_at = datetime.now()
            db.commit()
            db.refresh(case)
        return _to_detail(case, viewer=user)
