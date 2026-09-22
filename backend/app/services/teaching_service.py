"""
教学实训分享业务层
- 脱敏逻辑：从 ScreeningCase / TrainingCase 生成脱敏快照
- 临时分享 / 入库申请 / 审核 / 收回 / 下架
- 全程 OpLog 日志
"""

import json
from datetime import datetime, timedelta
from typing import Any, List, Optional

from fastapi import HTTPException, status
from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session

from app.db.models import (
    MessageTypeEnum,
    RoleEnum,
    ScreeningCase,
    ShareSourceEnum,
    ShareStatusEnum,
    ShareTypeEnum,
    TeachingShare,
    TrainingCase,
    User,
)
from app.schemas.teaching import (
    StudentCaseOut,
    StudentCasePage,
    TeachingReviewParams,
    TeachingShareCreate,
    TeachingShareOut,
    TeachingSharePage,
    TeachingSubmitCreate,
)
from app.services.op_log_service import OpLogService
from app.services.user_message_service import UserMessageService


def _desensitize_screening(case: ScreeningCase) -> dict:
    return {
        "title": f"教学病例-{case.case_no}",
        "description": "",
        "patient_age": case.age,
        "patient_gender": case.gender or "U",
        "clinical_info": f"{case.chief_complaint}\n{case.medical_history}".strip(),
        **_image_block(case.image_paths),
        "category": "DR",
        "difficulty": "MEDIUM",
    }


def _desensitize_training(case: TrainingCase) -> dict:
    return {
        "title": case.title,
        "description": case.description,
        "patient_age": case.patient_age,
        "patient_gender": case.patient_gender or "U",
        "clinical_info": case.clinical_info,
        "teaching_points": case.teaching_points or "",
        **_image_block(case.image_paths),
        "category": case.category,
        "difficulty": case.difficulty,
        "gold_dr_grade": case.gold_dr_grade,
        "gold_diagnosis": case.gold_diagnosis,
        "gold_lesions": case.gold_lesions,
        "gold_annotations": case.gold_annotations,
    }


def _flatten(image_paths) -> list:
    from app.common.case_utils import flatten_image_paths
    return flatten_image_paths(image_paths)


def _image_block(image_paths) -> dict:
    """同一文件挂在左右眼两栏时，列表和张数都按一张计。"""
    from app.common.case_utils import collapse_duplicate_image_paths
    paths = collapse_duplicate_image_paths(image_paths)
    return {
        "image_paths": paths,
        "image_count": len(_flatten(paths)),
    }


# IDRiD 导入用像素计数，HE 是出血；种子病例用处数，HE 是硬性渗出。
# 两套缩写不能混用，否则演示会把出血讲成硬渗。
_LESION_BY_PIXELS = {
    "MA": "微动脉瘤",
    "HE": "出血",
    "EX": "硬性渗出",
    "SE": "软性渗出",
}
_LESION_BY_COUNT = {
    "MA": "微动脉瘤",
    "HM": "出血",
    "HE": "硬性渗出",
    "NV": "新生血管",
    "VB": "静脉串珠",
    "IRMA": "视网膜内微血管异常",
    "OpticDiskCupping": "视盘陷凹扩大",
    "Drusen": "玻璃膜疣",
}
_CATEGORY_TEXT = {
    "DR": "糖尿病视网膜病变",
    "NORMAL": "正常眼底",
    "AMD": "年龄相关性黄斑变性",
    "GLAUCOMA": "青光眼",
    "HYPERTENSION": "高血压眼底",
    "OTHER": "其他",
}
_DIFFICULTY_TEXT = {
    "EASY": "入门",
    "MEDIUM": "中级",
    "HARD": "高级",
}


def _as_list(raw: Any) -> list:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            return []
    return raw if isinstance(raw, list) else []


def lesion_rows(raw: Any) -> list:
    """把库存病灶编码换成演示能直接念的中文。没有计数就不编造处数。"""
    rows = []
    for it in _as_list(raw):
        if not isinstance(it, dict):
            continue
        code = str(it.get("type") or it.get("label") or "").strip()
        if "pixel_count" in it:
            name = _LESION_BY_PIXELS.get(code, code or "病灶")
            detail = "着色图里有这块区域"
        else:
            name = _LESION_BY_COUNT.get(code, _LESION_BY_PIXELS.get(code, code or "病灶"))
            count = it.get("count")
            detail = f"约 {count} 处" if count else ""
        rows.append({"name": name, "detail": detail})
    return rows


def grade_line(category: Optional[str], raw: Optional[str]) -> str:
    from app.common.dr_grade import NOT_APPLICABLE_TEXT, grade_text, should_be_not_applicable

    if should_be_not_applicable(category, raw):
        return "本例不按 DR 分级"
    text = grade_text(raw)
    if not text or text == NOT_APPLICABLE_TEXT:
        return "本例不做 DR 分级"
    return text


def _training_case_for_share(db: Session, share: TeachingShare):
    if share.source_type != ShareSourceEnum.TRAINING.value:
        return None
    case = db.query(TrainingCase).filter(TrainingCase.id == share.source_case_id).first()
    if case is None and share.teaching_case_id:
        case = db.query(TrainingCase).filter(TrainingCase.id == share.teaching_case_id).first()
    return case


def _mask_url(db: Session, case_id: int) -> str:
    from app.services.practice_service import _lesion_mask_url
    return _lesion_mask_url(db, case_id)


def demo_fields(db: Session, share: TeachingShare, snapshot: dict) -> dict:
    """演示正文以仍在库里的实训病例为准。分享快照经常没存要点，标注框也是空的。"""
    case = _training_case_for_share(db, share)
    teaching_points = (snapshot.get("teaching_points") or "").strip()
    gold_diagnosis = snapshot.get("gold_diagnosis") or ""
    grade_raw = snapshot.get("gold_dr_grade") or ""
    category = snapshot.get("category") or ""
    difficulty = snapshot.get("difficulty") or ""
    lesions = snapshot.get("gold_lesions")
    annotations = snapshot.get("gold_annotations")
    mask = ""
    if case is not None:
        if (case.teaching_points or "").strip():
            teaching_points = case.teaching_points.strip()
        if case.gold_diagnosis:
            gold_diagnosis = case.gold_diagnosis
        if case.gold_dr_grade:
            grade_raw = case.gold_dr_grade
        if case.category:
            category = case.category
        if case.difficulty:
            difficulty = case.difficulty
        if case.gold_lesions:
            lesions = case.gold_lesions
        if _as_list(case.gold_annotations):
            annotations = case.gold_annotations
        mask = _mask_url(db, case.id)
    return {
        "teaching_points": teaching_points,
        "gold_diagnosis": gold_diagnosis or "",
        "gold_grade_text": grade_line(category, grade_raw),
        "category_text": _CATEGORY_TEXT.get(category, category or ""),
        "difficulty_text": _DIFFICULTY_TEXT.get(difficulty, difficulty or ""),
        "lesions": lesion_rows(lesions),
        "annotations": _as_list(annotations),
        "lesion_mask_url": mask,
    }


def _student_out(db: Session, share: TeachingShare) -> StudentCaseOut:
    data = dict(share.desensitized_data or {})
    demo = demo_fields(db, share, data)
    return StudentCaseOut(
        id=share.id,
        share_type=share.share_type,
        title=data.get("title", ""),
        description=data.get("description", ""),
        patient_age=data.get("patient_age"),
        patient_gender=data.get("patient_gender", "U"),
        clinical_info=data.get("clinical_info", ""),
        category=data.get("category", ""),
        difficulty=data.get("difficulty", ""),
        **_image_block(data.get("image_paths")),
        teacher_name=(share.teacher.real_name if share.teacher else ""),
        expired_at=share.expired_at,
        teaching_case_id=share.teaching_case_id,
        **demo,
    )


def _to_out(s: TeachingShare, db: Optional[Session] = None) -> TeachingShareOut:
    data = dict(s.desensitized_data or {})
    if db is not None:
        data.update(demo_fields(db, s, data))
    return TeachingShareOut(
        id=s.id,
        share_type=s.share_type,
        source_type=s.source_type,
        source_case_id=s.source_case_id,
        teaching_case_id=s.teaching_case_id,
        desensitized_data=data,
        share_scope=s.share_scope,
        expire_hours=s.expire_hours,
        expired_at=s.expired_at,
        status=s.status,
        review_comment=s.review_comment or "",
        reviewed_at=s.reviewed_at,
        reviewer_name=(s.reviewer.real_name if s.reviewer else ""),
        teacher_id=s.teacher_id,
        teacher_name=(s.teacher.real_name if s.teacher else ""),
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


class TeachingService:

    @staticmethod
    def _get_source_case(db: Session, source_type: str, source_case_id: int):
        if source_type == ShareSourceEnum.SCREENING.value:
            case = db.query(ScreeningCase).filter(ScreeningCase.id == source_case_id).first()
        else:
            case = db.query(TrainingCase).filter(TrainingCase.id == source_case_id).first()
        if not case:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "来源病例不存在")
        return case

    @staticmethod
    def _desensitize(source_type: str, case) -> dict:
        if source_type == ShareSourceEnum.SCREENING.value:
            return _desensitize_screening(case)
        return _desensitize_training(case)

    @staticmethod
    def create_temp_share(
        db: Session, *, user: User, params: TeachingShareCreate, ip: str = ""
    ) -> TeachingShareOut:
        case = TeachingService._get_source_case(db, params.source_type, params.source_case_id)
        data = TeachingService._desensitize(params.source_type, case)
        now = datetime.now()
        share = TeachingShare(
            share_type=ShareTypeEnum.TEMPORARY.value,
            source_type=params.source_type,
            source_case_id=params.source_case_id,
            desensitized_data=data,
            share_scope=params.share_scope,
            expire_hours=params.expire_hours,
            expired_at=now + timedelta(hours=params.expire_hours),
            status=ShareStatusEnum.SHARING.value,
            teacher_id=user.id,
        )
        db.add(share)
        db.flush()
        OpLogService.record(
            db, user=user, module="teaching", action="share_create",
            detail=f"临时分享病例 {params.source_type}#{params.source_case_id}，有效期{params.expire_hours}h",
            ip=ip, commit=False,
        )
        db.commit()
        db.refresh(share)
        return _to_out(share, db)

    @staticmethod
    def revoke_share(db: Session, *, user: User, share_id: int, ip: str = "") -> TeachingShareOut:
        share = db.query(TeachingShare).filter(TeachingShare.id == share_id).first()
        if not share:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "分享记录不存在")
        if share.teacher_id != user.id and user.role.code != RoleEnum.ADMIN.value:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "无权操作")
        if share.status != ShareStatusEnum.SHARING.value:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "当前状态不可收回")
        share.status = ShareStatusEnum.REVOKED.value
        OpLogService.record(
            db, user=user, module="teaching", action="share_revoke",
            detail=f"收回分享#{share_id}", ip=ip, commit=False,
        )
        db.commit()
        db.refresh(share)
        return _to_out(share, db)

    @staticmethod
    def submit_for_review(
        db: Session, *, user: User, params: TeachingSubmitCreate, ip: str = ""
    ) -> TeachingShareOut:
        case = TeachingService._get_source_case(db, params.source_type, params.source_case_id)
        data = TeachingService._desensitize(params.source_type, case)
        if params.title:
            data["title"] = params.title
        if params.description:
            data["description"] = params.description
        share = TeachingShare(
            share_type=ShareTypeEnum.PERMANENT.value,
            source_type=params.source_type,
            source_case_id=params.source_case_id,
            desensitized_data=data,
            share_scope="ALL",
            expire_hours=0,
            status=ShareStatusEnum.PENDING.value,
            teacher_id=user.id,
        )
        db.add(share)
        db.flush()
        OpLogService.record(
            db, user=user, module="teaching", action="submit_review",
            detail=f"提交入库申请 {params.source_type}#{params.source_case_id}",
            ip=ip, commit=False,
        )
        db.commit()
        db.refresh(share)
        return _to_out(share, db)

    @staticmethod
    def review(
        db: Session, *, reviewer: User, share_id: int, params: TeachingReviewParams, ip: str = ""
    ) -> TeachingShareOut:
        share = db.query(TeachingShare).filter(TeachingShare.id == share_id).first()
        if not share:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "记录不存在")
        if share.status != ShareStatusEnum.PENDING.value:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "当前状态不可审核")
        if not params.accept and not params.comment:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "驳回必须填写理由")

        now = datetime.now()
        share.reviewer_id = reviewer.id
        share.reviewed_at = now
        share.review_comment = params.comment

        if params.accept:
            share.status = ShareStatusEnum.APPROVED.value
            data = dict(share.desensitized_data or {})
            data.update(_image_block(data.get("image_paths")))
            share.desensitized_data = data
            from app.services.case_sn import generate_case_sn
            new_case = TrainingCase(
                case_no=generate_case_sn(db, prefix="T"),
                case_sn=generate_case_sn(db, prefix="CASE"),
                title=data.get("title", "教学病例"),
                description=data.get("description", ""),
                category=data.get("category", "DR"),
                difficulty=data.get("difficulty", "MEDIUM"),
                patient_name="教学病例",
                patient_age=data.get("patient_age"),
                patient_gender=data.get("patient_gender", "U"),
                patient_phone="",
                clinical_info=data.get("clinical_info", ""),
                teaching_points=data.get("teaching_points") or "",
                image_paths=data.get("image_paths"),
                gold_dr_grade=data.get("gold_dr_grade", "0"),
                gold_diagnosis=data.get("gold_diagnosis", ""),
                gold_lesions=data.get("gold_lesions"),
                gold_annotations=data.get("gold_annotations"),
                is_published=True,
                is_train_case=True,
                creator_id=share.teacher_id,
            )
            db.add(new_case)
            db.flush()
            share.teaching_case_id = new_case.id
            msg_title = "教学病例入库已通过"
            msg_content = f"您提交的病例「{data.get('title', '')}」已通过审核，已入库公共教学病例库。"
        else:
            share.status = ShareStatusEnum.REJECTED.value
            msg_title = "教学病例入库已驳回"
            msg_content = f"您提交的病例入库申请已被驳回。理由：{params.comment}"

        UserMessageService.push(
            db, user_id=share.teacher_id, msg_type=MessageTypeEnum.SYSTEM.value,
            title=msg_title, content=msg_content,
            ref_type="teaching_share", ref_id=share.id, commit=False,
        )
        action = "review_approve" if params.accept else "review_reject"
        OpLogService.record(
            db, user=reviewer, module="teaching", action=action,
            detail=f"审核分享#{share_id} {'通过' if params.accept else '驳回'}",
            ip=ip, commit=False,
        )
        db.commit()
        db.refresh(share)
        return _to_out(share, db)

    @staticmethod
    def shelve(db: Session, *, user: User, share_id: int, ip: str = "") -> TeachingShareOut:
        share = db.query(TeachingShare).filter(TeachingShare.id == share_id).first()
        if not share:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "记录不存在")
        if share.status != ShareStatusEnum.APPROVED.value:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "仅已通过的记录可下架")
        share.status = ShareStatusEnum.SHELVED.value
        if share.teaching_case_id:
            tc = db.query(TrainingCase).filter(TrainingCase.id == share.teaching_case_id).first()
            if tc:
                tc.is_published = False
                tc.is_train_case = False
        OpLogService.record(
            db, user=user, module="teaching", action="shelve",
            detail=f"下架教学病例 分享#{share_id}", ip=ip, commit=False,
        )
        db.commit()
        db.refresh(share)
        return _to_out(share, db)

    @staticmethod
    def list_for_teacher(
        db: Session, *, user: User, page: int = 1, page_size: int = 20,
        share_type: Optional[str] = None, status_filter: Optional[str] = None,
    ) -> TeachingSharePage:
        q = db.query(TeachingShare).filter(TeachingShare.teacher_id == user.id)
        if share_type:
            q = q.filter(TeachingShare.share_type == share_type)
        if status_filter:
            q = q.filter(TeachingShare.status == status_filter)
        total = q.count()
        rows = q.order_by(desc(TeachingShare.created_at)).offset((page - 1) * page_size).limit(page_size).all()
        return TeachingSharePage(total=total, page=page, page_size=page_size, list=[_to_out(r, db) for r in rows])

    @staticmethod
    def list_for_admin(
        db: Session, *, page: int = 1, page_size: int = 20,
        status_filter: Optional[str] = None, keyword: Optional[str] = None,
    ) -> TeachingSharePage:
        q = db.query(TeachingShare).filter(TeachingShare.share_type == ShareTypeEnum.PERMANENT.value)
        if status_filter:
            q = q.filter(TeachingShare.status == status_filter)
        if keyword:
            q = q.join(User, TeachingShare.teacher_id == User.id).filter(
                or_(User.real_name.contains(keyword), User.username.contains(keyword))
            )
        total = q.count()
        rows = q.order_by(desc(TeachingShare.created_at)).offset((page - 1) * page_size).limit(page_size).all()
        return TeachingSharePage(total=total, page=page, page_size=page_size, list=[_to_out(r, db) for r in rows])

    @staticmethod
    def list_for_student(
        db: Session, *, page: int = 1, page_size: int = 20,
    ) -> StudentCasePage:
        now = datetime.now()
        q = db.query(TeachingShare).filter(
            or_(
                (TeachingShare.share_type == ShareTypeEnum.TEMPORARY.value) &
                (TeachingShare.status == ShareStatusEnum.SHARING.value) &
                (TeachingShare.expired_at > now),
                (TeachingShare.share_type == ShareTypeEnum.PERMANENT.value) &
                (TeachingShare.status == ShareStatusEnum.APPROVED.value),
            )
        )
        total = q.count()
        rows = q.order_by(desc(TeachingShare.created_at)).offset((page - 1) * page_size).limit(page_size).all()
        items = [_student_out(db, s) for s in rows]
        return StudentCasePage(total=total, page=page, page_size=page_size, list=items)

    @staticmethod
    def get_student_case_detail(
        db: Session, *, share_id: int, user: User, ip: str = ""
    ) -> StudentCaseOut:
        now = datetime.now()
        share = db.query(TeachingShare).filter(TeachingShare.id == share_id).first()
        if not share:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "病例不存在")
        visible = False
        if share.share_type == ShareTypeEnum.TEMPORARY.value:
            visible = share.status == ShareStatusEnum.SHARING.value and share.expired_at and share.expired_at > now
        elif share.share_type == ShareTypeEnum.PERMANENT.value:
            visible = share.status == ShareStatusEnum.APPROVED.value
        if not visible:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "该病例不可访问")
        OpLogService.record(
            db, user=user, module="teaching", action="student_view",
            detail=f"学员查看演示病例#{share_id}", ip=ip, commit=True,
        )
        return _student_out(db, share)
