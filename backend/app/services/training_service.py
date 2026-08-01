"""
实训培训业务层
- 病例列表 / 详情
- 标注提交（IoU 计算 + 入库）
- 金标准 / 热力图
- IoU 历史 / 个人统计
- 标记完成

caseId 约定：
    前端使用字符串编号（CASE001 / T2026001 …），对应 DB 中 biz_training_case.case_no
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session

from app.db.models import (
    CaseCategoryEnum,
    CaseDifficultyEnum,
    RecordStatusEnum,
    RoleEnum,
    TrainingCase,
    TrainingRecord,
    User,
)
from app.schemas.training import (
    Annotation,
    AnnotationPoint,
    CaseListQuery,
    GoldStandardResult,
    HeatmapResult,
    Hotspot,
    IoUDetail,
    IoUResult,
    Lesion,
    PageResult,
    SubmitAnnotationParams,
    TrainingCaseOut,
    TrainingStats,
)


# ====================== 常量映射 ======================

DR_GRADE_TEXT: Dict[str, str] = {
    "0": "0 级 无 DR",
    "1": "1 级 轻度 NPDR",
    "2": "2 级 中度 NPDR",
    "3": "3 级 重度 NPDR",
    "4": "4 级 PDR（增殖性）",
}

DIFFICULTY_DB_TO_CN = {
    CaseDifficultyEnum.EASY.value: "入门",
    CaseDifficultyEnum.MEDIUM.value: "中级",
    CaseDifficultyEnum.HARD.value: "高级",
}
DIFFICULTY_CN_TO_DB = {
    "入门": CaseDifficultyEnum.EASY.value,
    "初级": CaseDifficultyEnum.EASY.value,
    "中级": CaseDifficultyEnum.MEDIUM.value,
    "高级": CaseDifficultyEnum.HARD.value,
}

GENDER_DB_TO_CN = {"M": "男", "F": "女", "U": "男"}


# ====================== 工具函数 ======================

def _get_case_or_404(db: Session, case_id: str) -> TrainingCase:
    case = db.query(TrainingCase).filter(TrainingCase.case_no == case_id).first()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"病例不存在：{case_id}",
        )
    return case


def _get_first_image(case: TrainingCase) -> Tuple[str, str]:
    """从 image_paths JSON 拿到 (image_url, thumb_url)"""
    paths = case.image_paths or {}
    img = ""
    if isinstance(paths, dict):
        for side in ("OD", "OS", "OU"):
            arr = paths.get(side) or []
            if arr:
                img = arr[0]
                break
    return img, img  # 缩略图先复用原图


def _eye_of_case(case: TrainingCase) -> str:
    paths = case.image_paths or {}
    if isinstance(paths, dict):
        if paths.get("OD") and paths.get("OS"):
            return "OU"
        if paths.get("OD"):
            return "OD"
        if paths.get("OS"):
            return "OS"
    return "OU"


def _best_iou_for_user(db: Session, user_id: int, case_pk: int) -> Optional[float]:
    val: Optional[float] = (
        db.query(func.max(TrainingRecord.iou_avg))
        .filter(
            TrainingRecord.user_id == user_id,
            TrainingRecord.case_id == case_pk,
            TrainingRecord.status.in_([
                RecordStatusEnum.SUBMITTED.value,
                RecordStatusEnum.GRADED.value,
                RecordStatusEnum.REVIEWED.value,
            ]),
        )
        .scalar()
    )
    return float(val) if val is not None else None


def _is_done(db: Session, user_id: int, case_pk: int) -> bool:
    cnt: int = (
        db.query(func.count(TrainingRecord.id))
        .filter(
            TrainingRecord.user_id == user_id,
            TrainingRecord.case_id == case_pk,
            TrainingRecord.status.in_([
                RecordStatusEnum.SUBMITTED.value,
                RecordStatusEnum.GRADED.value,
                RecordStatusEnum.REVIEWED.value,
            ]),
        )
        .scalar()
    )
    return bool(cnt and cnt > 0)


def _to_case_out(
    db: Session,
    case: TrainingCase,
    user_id: int,
) -> TrainingCaseOut:
    image_url, thumb_url = _get_first_image(case)

    lesions_raw = case.gold_lesions or []
    lesions: List[Lesion] = []
    if isinstance(lesions_raw, list):
        for it in lesions_raw:
            if not isinstance(it, dict):
                continue
            try:
                lesions.append(
                    Lesion(
                        type=it.get("type") or "微动脉瘤",
                        count=int(it.get("count") or 0),
                        location=it.get("location", "") or "",
                    )
                )
            except Exception:
                continue

    diff_cn = DIFFICULTY_DB_TO_CN.get(case.difficulty, "入门")
    return TrainingCaseOut(
        id=case.case_no,
        name=f"病例-{case.case_no}",
        age=case.patient_age or 0,
        gender=GENDER_DB_TO_CN.get(case.patient_gender, "男"),
        eye=_eye_of_case(case),
        dr_grade=DR_GRADE_TEXT.get(case.gold_dr_grade, ""),
        dr_level=int(case.gold_dr_grade) if (case.gold_dr_grade or "0").isdigit() else 0,
        difficulty=diff_cn,
        done=_is_done(db, user_id, case.id),
        thumb_url=thumb_url or None,
        image_url=image_url or None,
        diabetes_years=0,
        hospital="",
        best_iou=_best_iou_for_user(db, user_id, case.id),
        lesions=lesions,
        created_at=case.created_at.strftime("%Y-%m-%d %H:%M:%S") if case.created_at else None,
    )


# ====================== IoU 计算 ======================

def _bbox_of(points: List[AnnotationPoint]) -> Optional[Tuple[float, float, float, float]]:
    """从点列表得到外接矩形 (x1,y1,x2,y2)"""
    if not points:
        return None
    xs = [p.x for p in points]
    ys = [p.y for p in points]
    return (min(xs), min(ys), max(xs), max(ys))


def _iou_box(a, b) -> float:
    ix1 = max(a[0], b[0])
    iy1 = max(a[1], b[1])
    ix2 = min(a[2], b[2])
    iy2 = min(a[3], b[3])
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = area_a + area_b - inter
    return float(inter / union) if union > 0 else 0.0


def _annotations_from_gold(case: TrainingCase) -> List[Annotation]:
    """金标准 JSON → Annotation 列表"""
    raw = case.gold_annotations or []
    out: List[Annotation] = []
    if not isinstance(raw, list):
        return out
    for idx, it in enumerate(raw):
        if not isinstance(it, dict):
            continue
        try:
            t = it.get("type") or "rect"
            label = it.get("label") or "微动脉瘤"

            # 兼容两种 JSON 形式：
            # 1) {"type":"box","label":"MA","x":120,"y":230,"w":18,"h":18}
            # 2) {"type":"rect","label":"出血","points":[{"x":..,"y":..}, ...]}
            if "points" in it and isinstance(it["points"], list):
                points = [
                    AnnotationPoint(x=float(p.get("x", 0)), y=float(p.get("y", 0)))
                    for p in it["points"] if isinstance(p, dict)
                ]
                ann_type = t if t in ("rect", "polygon", "pen") else "rect"
            else:
                x = float(it.get("x", 0))
                y = float(it.get("y", 0))
                w = float(it.get("w", 0))
                h = float(it.get("h", 0))
                points = [
                    AnnotationPoint(x=x, y=y),
                    AnnotationPoint(x=x + w, y=y + h),
                ]
                ann_type = "rect"

            out.append(Annotation(
                id=f"GOLD_{idx + 1}",
                server_id=str(idx + 1),
                type=ann_type,
                points=points,
                label=label if label in ("出血", "渗出", "微动脉瘤", "棉绒斑", "新生血管") else "微动脉瘤",
                color=it.get("color"),
                remark=it.get("remark"),
            ))
        except Exception:
            continue
    return out


def _compute_iou(
    student: List[Annotation],
    gold: List[Annotation],
    iou_threshold: float = 0.3,
) -> Tuple[float, List[IoUDetail]]:
    """
    按 label 分桶，逐病灶分类计算：
        平均 IoU、recall（命中数）、missed（漏标）、falsePositive（误标）
    """
    labels = {a.label for a in student} | {g.label for g in gold}
    details: List[IoUDetail] = []
    iou_sum = 0.0
    iou_cnt = 0

    for label in labels:
        s_boxes = [b for b in (_bbox_of(a.points) for a in student if a.label == label) if b]
        g_boxes = [b for b in (_bbox_of(g.points) for g in gold if g.label == label) if b]

        used_g = set()
        ious: List[float] = []
        recall = 0
        for sb in s_boxes:
            best_iou = 0.0
            best_idx = -1
            for gi, gb in enumerate(g_boxes):
                if gi in used_g:
                    continue
                v = _iou_box(sb, gb)
                if v > best_iou:
                    best_iou = v
                    best_idx = gi
            if best_iou >= iou_threshold and best_idx >= 0:
                used_g.add(best_idx)
                ious.append(best_iou)
                recall += 1
            else:
                ious.append(0.0)

        missed = len(g_boxes) - recall
        false_positive = len(s_boxes) - recall
        avg = (sum(ious) / len(ious)) if ious else 0.0

        details.append(IoUDetail(
            label=label,
            iou=round(avg, 4),
            recall=recall,
            missed=max(0, missed),
            false_positive=max(0, false_positive),
        ))

        if ious:
            iou_sum += avg
            iou_cnt += 1

    overall = round(iou_sum / iou_cnt, 4) if iou_cnt else 0.0
    return overall, details


def _grade_of(iou: float):
    if iou >= 0.85:
        return "A+"
    if iou >= 0.7:
        return "A"
    if iou >= 0.5:
        return "B"
    return "C"


def _comment_of(iou: float, missed: int, false_positive: int) -> str:
    if iou >= 0.85:
        return "标注质量优秀，与金标准高度一致。"
    if iou >= 0.7:
        return "标注总体准确，建议关注边界精度与极小病灶。"
    if iou >= 0.5:
        return f"标注基本到位，但存在 {missed} 处漏标 / {false_positive} 处误标，请结合金标准复核。"
    return "标注与金标准差距较大，建议重新阅片并参考热力图。"


# ====================== Service ======================

class TrainingService:

    # -------- 病例 --------

    @staticmethod
    def list_cases(db: Session, user: User, query: CaseListQuery) -> PageResult:
        q = db.query(TrainingCase).filter(TrainingCase.is_published == True)  # noqa: E712

        if query.keyword:
            kw = f"%{query.keyword.strip()}%"
            q = q.filter(
                or_(
                    TrainingCase.case_no.like(kw),
                    TrainingCase.title.like(kw),
                    TrainingCase.description.like(kw),
                )
            )
        if query.dr_level is not None:
            q = q.filter(TrainingCase.gold_dr_grade == str(query.dr_level))
        if query.difficulty:
            db_diff = DIFFICULTY_CN_TO_DB.get(query.difficulty)
            if db_diff:
                q = q.filter(TrainingCase.difficulty == db_diff)

        total = q.count()
        rows: List[TrainingCase] = (
            q.order_by(desc(TrainingCase.id))
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
            .all()
        )

        cases = [_to_case_out(db, c, user.id) for c in rows]

        if query.done is not None:
            cases = [c for c in cases if c.done == query.done]

        return PageResult(
            total=total,
            page=query.page,
            page_size=query.page_size,
            list=cases,
        )

    @staticmethod
    def get_case(db: Session, user: User, case_id: str) -> TrainingCaseOut:
        case = _get_case_or_404(db, case_id)
        return _to_case_out(db, case, user.id)

    @staticmethod
    def mark_case_done(db: Session, user: User, case_id: str) -> None:
        case = _get_case_or_404(db, case_id)

        record: Optional[TrainingRecord] = (
            db.query(TrainingRecord)
            .filter(
                TrainingRecord.user_id == user.id,
                TrainingRecord.case_id == case.id,
            )
            .order_by(desc(TrainingRecord.id))
            .first()
        )
        if record is None:
            record = TrainingRecord(
                user_id=user.id,
                case_id=case.id,
                attempt_no=1,
                status=RecordStatusEnum.SUBMITTED.value,
                student_diagnosis="",
                teacher_comment="",
                submitted_at=datetime.now(),
            )
            db.add(record)
        else:
            if record.status == RecordStatusEnum.DRAFT.value:
                record.status = RecordStatusEnum.SUBMITTED.value
                record.submitted_at = datetime.now()
        db.commit()

    # -------- 热力图 --------

    @staticmethod
    def get_heatmap(db: Session, case_id: str) -> HeatmapResult:
        case = _get_case_or_404(db, case_id)

        hotspots: List[Hotspot] = []
        for ann in _annotations_from_gold(case):
            box = _bbox_of(ann.points)
            if not box:
                continue
            cx = (box[0] + box[2]) / 2
            cy = (box[1] + box[3]) / 2
            radius = max(box[2] - box[0], box[3] - box[1]) / 2 or 12.0
            hotspots.append(Hotspot(
                x=round(cx, 2),
                y=round(cy, 2),
                radius=round(radius, 2),
                score=0.9,
                label=ann.label,
            ))

        return HeatmapResult(
            case_id=case.case_no,
            heatmap_url=case.gold_heatmap_path or "",
            hotspots=hotspots,
        )

    # -------- 金标准 --------

    @staticmethod
    def get_gold(db: Session, case_id: str, user: "User" = None) -> GoldStandardResult:
        """
        获取金标准标注。

        盲训门禁（报告 P0）：学员必须先提交过本病例的作答才能查看金标准。
        此前本接口只校验角色、不校验作答状态，任何登录学员可在作答前直接取回
        任意病例的金标准，导致训练与考核效度失真。
        """
        case = _get_case_or_404(db, case_id)

        if user is not None:
            role_code = user.role.code if user.role else None
            if role_code not in (RoleEnum.TEACHER.value, RoleEnum.ADMIN.value):
                from app.db.models.practice_session import (
                    PracticeSession,
                    PracticeStatusEnum,
                )

                submitted = (
                    db.query(PracticeSession.id)
                    .filter(
                        PracticeSession.user_id == user.id,
                        PracticeSession.case_id == case.id,
                        PracticeSession.status.in_([
                            PracticeStatusEnum.SUBMITTED.value,
                            PracticeStatusEnum.REVIEWED.value,
                        ]),
                    )
                    .first()
                )
                if not submitted:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="请先提交本次作答，才能查看金标准",
                    )

        return GoldStandardResult(
            case_id=case.case_no,
            annotations=_annotations_from_gold(case),
        )

    # -------- 提交标注 --------

    @staticmethod
    def submit_annotation(
        db: Session,
        user: User,
        params: SubmitAnnotationParams,
        persist: bool,
    ) -> IoUResult:
        case = _get_case_or_404(db, params.case_id)
        gold = _annotations_from_gold(case)

        overall_iou, details = _compute_iou(params.annotations, gold)
        missed = sum(d.missed for d in details)
        false_positive = sum(d.false_positive for d in details)
        grade = _grade_of(overall_iou)
        comment = _comment_of(overall_iou, missed, false_positive)
        now = datetime.now()
        submitted_at_str = now.strftime("%Y-%m-%d %H:%M:%S")

        if persist:
            attempt_no: int = (
                db.query(func.coalesce(func.max(TrainingRecord.attempt_no), 0))
                .filter(
                    TrainingRecord.user_id == user.id,
                    TrainingRecord.case_id == case.id,
                )
                .scalar()
            ) + 1

            score_total = round(overall_iou * 100, 2)
            score_pass = score_total >= (case.pass_score or 60)

            student_anns_json = [
                {
                    "id": a.id,
                    "type": a.type,
                    "label": a.label,
                    "points": [{"x": p.x, "y": p.y} for p in a.points],
                    "color": a.color,
                    "remark": a.remark,
                }
                for a in params.annotations
            ]

            record = TrainingRecord(
                user_id=user.id,
                case_id=case.id,
                attempt_no=attempt_no,
                status=RecordStatusEnum.GRADED.value,
                student_dr_grade="",
                student_diagnosis="",
                student_lesions=[],
                student_annotations=student_anns_json,
                grade_score=0.0,
                annotation_score=score_total,
                diagnosis_score=0.0,
                total_score=score_total,
                iou_avg=round(overall_iou, 4),
                is_passed=1 if score_pass else 0,
                duration_seconds=params.duration_sec or 0,
                started_at=now,
                submitted_at=now,
                graded_at=now,
                teacher_comment=comment,
            )
            db.add(record)
            db.commit()

        return IoUResult(
            case_id=case.case_no,
            iou=overall_iou,
            details=details,
            grade=grade,
            comment=comment,
            submitted_at=submitted_at_str,
        )

    # -------- IoU 历史 --------

    @staticmethod
    def iou_history(db: Session, user: User, case_id: str) -> List[IoUResult]:
        case = _get_case_or_404(db, case_id)
        rows: List[TrainingRecord] = (
            db.query(TrainingRecord)
            .filter(
                TrainingRecord.user_id == user.id,
                TrainingRecord.case_id == case.id,
                TrainingRecord.status.in_([
                    RecordStatusEnum.GRADED.value,
                    RecordStatusEnum.SUBMITTED.value,
                    RecordStatusEnum.REVIEWED.value,
                ]),
            )
            .order_by(desc(TrainingRecord.id))
            .all()
        )
        out: List[IoUResult] = []
        for r in rows:
            iou_val = float(r.iou_avg or 0.0)
            out.append(IoUResult(
                case_id=case.case_no,
                iou=round(iou_val, 4),
                details=[],
                grade=_grade_of(iou_val),
                comment=r.teacher_comment or "",
                submitted_at=(r.submitted_at or r.created_at).strftime("%Y-%m-%d %H:%M:%S"),
            ))
        return out

    # -------- 个人统计 --------

    @staticmethod
    def stats(db: Session, user: User) -> TrainingStats:
        total_cases: int = (
            db.query(func.count(TrainingCase.id))
            .filter(TrainingCase.is_published == True)  # noqa: E712
            .scalar()
        ) or 0

        done_cases: int = (
            db.query(func.count(func.distinct(TrainingRecord.case_id)))
            .filter(
                TrainingRecord.user_id == user.id,
                TrainingRecord.status.in_([
                    RecordStatusEnum.SUBMITTED.value,
                    RecordStatusEnum.GRADED.value,
                    RecordStatusEnum.REVIEWED.value,
                ]),
            )
            .scalar()
        ) or 0

        avg_iou = db.query(func.avg(TrainingRecord.iou_avg)).filter(
            TrainingRecord.user_id == user.id,
            TrainingRecord.status != RecordStatusEnum.DRAFT.value,
        ).scalar()

        best_iou = db.query(func.max(TrainingRecord.iou_avg)).filter(
            TrainingRecord.user_id == user.id,
            TrainingRecord.status != RecordStatusEnum.DRAFT.value,
        ).scalar()

        total_anns: int = 0
        total_duration: int = (
            db.query(func.coalesce(func.sum(TrainingRecord.duration_seconds), 0))
            .filter(TrainingRecord.user_id == user.id)
            .scalar()
        ) or 0

        records: List[TrainingRecord] = (
            db.query(TrainingRecord)
            .filter(TrainingRecord.user_id == user.id)
            .all()
        )
        for r in records:
            anns = r.student_annotations or []
            if isinstance(anns, list):
                total_anns += len(anns)

        return TrainingStats(
            total_cases=total_cases,
            done_cases=done_cases,
            avg_iou=round(float(avg_iou or 0.0), 4),
            best_iou=round(float(best_iou or 0.0), 4),
            total_annotations=total_anns,
            total_duration=int(total_duration),
        )
