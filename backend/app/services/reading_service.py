"""
影像阅片业务层
- 读取病例影像源（基于 TrainingCase.image_paths）
- 保存 / 查询 / 提交 / 审核 阅片标注集合
- 角色权限：
    STUDENT  → 只能读写自己的 DRAFT；submit 自己；不能审核
    TEACHER  → 自己创建的全部 + 学员已提交可审核；可审核已 SUBMITTED 的
    ADMIN    → 所有
"""

from datetime import datetime
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from app.db.models import (
    ReadingAnnotation,
    ReadingStatusEnum,
    RoleEnum,
    TrainingCase,
    User,
)
from app.common import workflow
from app.common.image_safety import (
    DEFAULT_MODALITY,
    DEFAULT_MODALITY_TEXT,
    build_image_meta,
    summarize_safety,
)
from app.services.op_log_service import OpLogService
from app.schemas.reading import (
    ImageSource,
    ReadingListQuery,
    ReadingOut,
    ReadingPage,
    ReadingReviewParams,
    ReadingSaveParams,
)


def _flatten_images(image_paths: Optional[dict]) -> List[dict]:
    if not isinstance(image_paths, dict):
        return []
    out: List[dict] = []
    idx = 0
    for side in ("OD", "OS", "OU"):
        arr = image_paths.get(side) or []
        if isinstance(arr, list):
            for url in arr:
                if isinstance(url, str) and url:
                    out.append({"index": idx, "url": url, "side": side})
                    idx += 1
    return out


def _to_out(record: ReadingAnnotation) -> ReadingOut:
    case_no = record.case.case_no if record.case else ""
    user_name = ""
    if record.user is not None:
        user_name = record.user.real_name or record.user.username
    reviewer_name = ""
    if record.reviewer is not None:
        reviewer_name = record.reviewer.real_name or record.reviewer.username

    return ReadingOut(
        id=record.id,
        case_id=record.case_id,
        case_no=case_no,
        user_id=record.user_id,
        user_name=user_name,
        image_index=record.image_index or 0,
        image_url=record.image_url or "",
        viewport=record.viewport,
        annotations=record.annotations or [],
        measurements=record.measurements or [],
        layers=record.layers,
        status=record.status,  # type: ignore[arg-type]
        diagnosis=record.diagnosis or {},
        note=record.note or "",
        review_comment=record.review_comment or "",
        reviewer_id=record.reviewer_id,
        reviewer_name=reviewer_name,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _get_case(db: Session, case_id: int) -> TrainingCase:
    case = db.query(TrainingCase).filter(TrainingCase.id == case_id).first()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"病例不存在：{case_id}",
        )
    return case


def _is_teacher_or_admin(user: User) -> bool:
    code = user.role.code if user.role else None
    return code in (RoleEnum.TEACHER.value, RoleEnum.ADMIN.value)


def _patient_block(case: TrainingCase, viewer: User) -> dict:
    """
    阅片页患者信息脱敏块。
    - 管理员：完整手机号
    - 教师：手机号脱敏
    - 学员 / 其他：手机号置空
    """
    from app.common.case_utils import mask_phone_by_role
    role = viewer.role.code if viewer.role else None
    phone, visible = mask_phone_by_role(getattr(case, "patient_phone", "") or "", role)
    return {
        "patient_name": getattr(case, "patient_name", "") or "",
        "patient_gender": case.patient_gender or "U",
        "patient_age": case.patient_age or 0,
        "patient_phone": phone,
        "phone_visible": visible,
    }


class ReadingService:

    # ---------- 影像源 ----------

    @staticmethod
    def get_image_source(db: Session, user: User, case_id: int) -> ImageSource:
        from collections import defaultdict
        from app.db.models import CaseImage
        from app.services.case_image_service import CaseImageService

        case = _get_case(db, case_id)

        # 学员：必须 published + ACTIVE
        if not _is_teacher_or_admin(user):
            from app.db.models import CaseArchiveStatusEnum
            if (
                not case.is_published
                or case.archive_status == CaseArchiveStatusEnum.ARCHIVED.value
            ):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="病例不存在或当前不可访问",
                )

        # 1) 老 image_paths 字段
        meta = _flatten_images(case.image_paths)
        legacy_images = [m["url"] for m in meta]

        # 2) 新 biz_case_image 一对多
        ci_records = CaseImageService.list_by_case(
            db, case_table="training", case_id=case.id,
        )
        groups: dict = defaultdict(list)
        for r in ci_records:
            groups[r.role].append(r.file_url)

        # 学员可见性：仅当已对该病例 SUBMITTED 或 REVIEWED 才解锁金标准 mask
        gold_roles = {"MA", "HE", "EX", "SE", "OD", "color_mask", "overlay", "class_mask"}
        show_gold = _is_teacher_or_admin(user)
        if not show_gold:
            from app.db.models.reading_annotation import ReadingAnnotation, ReadingStatusEnum
            submitted = (
                db.query(ReadingAnnotation.id)
                .filter(
                    ReadingAnnotation.case_id == case.id,
                    ReadingAnnotation.user_id == user.id,
                    ReadingAnnotation.status.in_([
                        ReadingStatusEnum.SUBMITTED.value,
                        ReadingStatusEnum.REVIEWED.value,
                    ]),
                )
                .first()
            )
            if submitted:
                show_gold = True

        if not show_gold:
            for r in list(groups.keys()):
                if r in gold_roles:
                    groups.pop(r, None)

        # 影像完整性
        comp = CaseImageService.case_completeness(
            db, case_table="training", case_id=case.id,
        )

        # 「images」一维：原图优先；若新表无原图，回退老 image_paths
        images = list(groups.get("original") or legacy_images)
        # 把 original 之外的全部 role 顺序追加到 images 末尾，便于旧客户端切换
        for r in ["MA", "HE", "EX", "SE", "OD", "color_mask", "overlay", "class_mask"]:
            for u in groups.get(r, []):
                if u not in images:
                    images.append(u)
        if not images:
            images = legacy_images

        # ============ 安全标识（报告 P0/P1） ============
        # 元数据优先取自 biz_case_image（含眼别与影像角色），
        # 老病例回退到 image_paths；两者都会做眼别交叉校验。
        visible_records = [r for r in ci_records if r.role in groups]
        # 质量结果为派生对象，单独查表；缺失即「未评估」，不伪造合格
        from app.services.image_quality_service import ImageQualityService
        q_map = ImageQualityService.quality_map(
            db, [r.id for r in visible_records],
        )
        safety_meta = build_image_meta(
            records=visible_records, legacy=meta, quality_map=q_map,
        )
        safety = summarize_safety(safety_meta)

        # PACS 对照。PACS 不可用不能影响阅片 —— 取不到就当没有 DICOM，
        # 前端照常用 JPG，而不是让整页打不开。
        dicom_instances: dict = {}
        segmentation = None
        try:
            from app.common.dicom_link import match_instances
            from app.services import dicomweb_client

            summary = dicomweb_client.study_summary(case.case_no)
            dicom_instances = match_instances(
                case_no=case.case_no,
                records=[r for r in ci_records if r.role == "original"],
                pacs_sop_uids=[i.get("sopInstanceUid") for i in summary.get("images", [])],
            )
            # 分割即金标准，与 mask 图层同一条可见性规则：
            # 未解锁时连 SOP UID 都不下发，否则等于把取答案的入口递出去
            if show_gold:
                segs = summary.get("segmentations") or []
                if segs:
                    segmentation = {
                        "sopInstanceUid": segs[0].get("sopInstanceUid"),
                        "segments": segs[0].get("segments") or [],
                    }
        except Exception:
            dicom_instances = {}
            segmentation = None

        return ImageSource(
            case_id=case.id,
            case_no=case.case_no,
            case_sn=getattr(case, "case_sn", "") or "",
            width=1024,
            height=1024,
            images=images,
            image_meta=safety_meta,
            image_groups=dict(groups),
            modality=DEFAULT_MODALITY,
            modality_text=DEFAULT_MODALITY_TEXT,
            # 现有数据模型没有采集检查日期字段；此处如实返回未知，
            # 不用 created_at（入库时间）冒充检查日期。
            # DICOM 化迁移时由 AcquisitionDateTime 回填。
            exam_date=None,
            exam_date_known=False,
            safety=safety,
            image_complete=bool(comp["complete"]),
            missing_roles=list(comp["missing_roles"]),
            show_gold_layers=show_gold,
            dicom_instances=dicom_instances,
            segmentation=segmentation,
            **_patient_block(case, user),
        )

    # ---------- 保存 / 提交 ----------

    @staticmethod
    def save(db: Session, user: User, params: ReadingSaveParams) -> ReadingOut:
        case = _get_case(db, params.case_id)

        # 学员：必须可见
        if not _is_teacher_or_admin(user):
            from app.db.models import CaseArchiveStatusEnum
            if (
                not case.is_published
                or case.archive_status == CaseArchiveStatusEnum.ARCHIVED.value
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="该病例当前不可写入",
                )

        # ---- 提交前校验结构化结论（报告 P1）----
        # 草稿允许不完整，正式提交必须结构化完备：否则结论仍旧
        # 难评分、难审计、难统计，等于没改。
        if params.submit:
            from app.common import diagnosis_form

            problems = diagnosis_form.validate(case.category, params.diagnosis)
            if problems:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "code": "DIAGNOSIS_INCOMPLETE",
                        "message": "诊断结论不完整，无法提交",
                        "problems": problems,
                    },
                )

        # 断网重试：上一次提交其实成功了，只是响应没回来。
        # 此时该记录已是 SUBMITTED，下面的草稿查询会落空并新建一条，
        # 同一份阅片就变成两条。同键先回放，不再重复落库。
        if params.submit and params.request_id:
            replay = (
                db.query(ReadingAnnotation)
                .filter(
                    ReadingAnnotation.user_id == user.id,
                    ReadingAnnotation.case_id == case.id,
                    ReadingAnnotation.image_index == params.image_index,
                    ReadingAnnotation.submit_request_id == params.request_id,
                )
                .order_by(desc(ReadingAnnotation.id))
                .first()
            )
            if replay is not None:
                return _to_out(replay)

        # 复用同一用户 + 同一病例 + 同一影像 的最近一条可编辑记录；否则新建。
        # 被驳回的记录也算可编辑 —— 驳回的意义就是让学员改完再交，
        # 若不复用，学员一改就变成新的一条，教师看不出这是上次那份的修订。
        record: Optional[ReadingAnnotation] = (
            db.query(ReadingAnnotation)
            .filter(
                ReadingAnnotation.user_id == user.id,
                ReadingAnnotation.case_id == case.id,
                ReadingAnnotation.image_index == params.image_index,
                ReadingAnnotation.status.in_([
                    ReadingStatusEnum.DRAFT.value,
                    ReadingStatusEnum.REJECTED.value,
                ]),
            )
            .order_by(desc(ReadingAnnotation.id))
            .first()
        )
        if record is None:
            record = ReadingAnnotation(
                case_id=case.id,
                user_id=user.id,
                image_index=params.image_index,
                image_url=params.image_url,
                annotations=[],
                measurements=[],
                status=ReadingStatusEnum.DRAFT.value,
            )
            db.add(record)

        record.image_url = params.image_url or record.image_url
        record.viewport = params.viewport.model_dump(by_alias=False) if params.viewport else None
        record.layers = params.layers.model_dump(by_alias=False) if params.layers else None
        record.annotations = [a.model_dump(by_alias=False) for a in params.annotations]
        record.measurements = [m.model_dump(by_alias=False) for m in params.measurements]
        record.diagnosis = params.diagnosis or {}
        record.note = params.note or ""

        before = record.status
        if params.submit:
            workflow.READING.ensure(before, ReadingStatusEnum.SUBMITTED.value)
            record.status = ReadingStatusEnum.SUBMITTED.value
            record.submit_request_id = params.request_id or None

        record.updated_at = datetime.now()
        db.commit()
        db.refresh(record)

        if params.submit:
            OpLogService.record(
                db,
                user=user,
                module="reading",
                action="submit",
                detail=workflow.transition_detail(
                    workflow.READING, record.id,
                    before, ReadingStatusEnum.SUBMITTED.value,
                    extra=f"病例 {case.id} 第 {record.image_index + 1} 张",
                ),
            )
        return _to_out(record)

    # ---------- 查询 ----------

    @staticmethod
    def list_records(db: Session, user: User, query: ReadingListQuery) -> ReadingPage:
        q = db.query(ReadingAnnotation)

        if query.case_id is not None:
            q = q.filter(ReadingAnnotation.case_id == query.case_id)
        if query.status:
            q = q.filter(ReadingAnnotation.status == query.status)

        # 权限范围
        if _is_teacher_or_admin(user):
            if query.user_id is not None:
                q = q.filter(ReadingAnnotation.user_id == query.user_id)
        else:
            # 学员：只能看自己的
            q = q.filter(ReadingAnnotation.user_id == user.id)

        total = q.count()
        rows = (
            q.order_by(desc(ReadingAnnotation.id))
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
            .all()
        )

        return ReadingPage(
            total=total,
            page=query.page,
            page_size=query.page_size,
            list=[_to_out(r) for r in rows],
        )

    @staticmethod
    def get_detail(db: Session, user: User, record_id: int) -> ReadingOut:
        record = (
            db.query(ReadingAnnotation)
            .filter(ReadingAnnotation.id == record_id)
            .first()
        )
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"阅片记录不存在：{record_id}",
            )

        # 学员只能看自己的
        if not _is_teacher_or_admin(user) and record.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权查看该阅片记录",
            )

        return _to_out(record)

    @staticmethod
    def get_latest_draft(
        db: Session,
        user: User,
        case_id: int,
        image_index: int,
    ) -> Optional[ReadingOut]:
        """获取当前用户在该病例 + 该影像下的最新草稿（用于阅片页"恢复未保存"）"""
        record = (
            db.query(ReadingAnnotation)
            .filter(
                ReadingAnnotation.user_id == user.id,
                ReadingAnnotation.case_id == case_id,
                ReadingAnnotation.image_index == image_index,
            )
            .order_by(desc(ReadingAnnotation.id))
            .first()
        )
        if not record:
            return None
        return _to_out(record)

    # ---------- 教师审核 ----------

    @staticmethod
    def review(
        db: Session,
        user: User,
        record_id: int,
        params: ReadingReviewParams,
    ) -> ReadingOut:
        if not _is_teacher_or_admin(user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="仅带教医师 / 管理员可审核",
            )

        record = (
            db.query(ReadingAnnotation)
            .filter(ReadingAnnotation.id == record_id)
            .first()
        )
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"阅片记录不存在：{record_id}",
            )

        # 通过与驳回都必须从「待审核」出发。
        # 原先只有驳回分支校验了状态，通过分支没校验 ——
        # 教师能直接通过一份从未提交的草稿，跳过学员提交这一环。
        target = (
            ReadingStatusEnum.REVIEWED.value
            if params.accept
            else ReadingStatusEnum.REJECTED.value
        )
        before = record.status
        workflow.READING.ensure(before, target)

        record.review_comment = params.review_comment or ""
        record.reviewer_id = user.id
        record.status = target
        record.updated_at = datetime.now()
        db.commit()
        db.refresh(record)

        OpLogService.record(
            db,
            user=user,
            module="reading",
            action="review",
            detail=workflow.transition_detail(
                workflow.READING, record.id, before, target,
                extra=f"学员 {record.user_id}",
            ),
        )
        return _to_out(record)

    # ---------- 删除（学员只能删自己的草稿） ----------

    @staticmethod
    def delete(db: Session, user: User, record_id: int) -> None:
        record = (
            db.query(ReadingAnnotation)
            .filter(ReadingAnnotation.id == record_id)
            .first()
        )
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"阅片记录不存在：{record_id}",
            )

        is_self = record.user_id == user.id
        is_admin = (user.role.code if user.role else "") == RoleEnum.ADMIN.value

        if not (is_admin or (is_self and record.status == ReadingStatusEnum.DRAFT.value)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="仅可删除本人草稿，或由管理员删除",
            )

        db.delete(record)
        db.commit()
