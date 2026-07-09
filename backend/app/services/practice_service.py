"""
学员自主练习业务层
- 病例随机抽取 / 指定病例
- 金标准查询
- 自主标注 → 提交后自动评分（IoU 比对 + 分级一致性 + 诊断匹配）
- 错误点位 / 漏诊 / 误诊 / 学习建议
- 个人台账 / 教师统计
"""

from datetime import datetime
from random import shuffle
from typing import List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session

from app.db.models import (
    CaseArchiveStatusEnum,
    PracticeModeEnum,
    PracticeSession,
    PracticeStatusEnum,
    RoleEnum,
    TrainingCase,
    User,
)
from app.schemas.practice import (
    CaseBriefForPractice,
    ErrorPoint,
    GoldStandardData,
    Point2D,
    PracticeAnnotation,
    PracticeListQuery,
    PracticeOut,
    PracticePage,
    PracticeRandomQuery,
    PracticeReviewParams,
    PracticeStartParams,
    PracticeStats,
    PracticeSubmitParams,
    WeakLabelItem,
)

CATEGORY_TEXT = {
    "DR": "糖尿病视网膜病变",
    "AMD": "老年性黄斑变性",
    "GLAUCOMA": "青光眼",
    "HYPERTENSION": "高血压性视网膜病变",
    "NORMAL": "正常眼底",
    "OTHER": "其他",
}

DIFFICULTY_TEXT = {"EASY": "入门", "MEDIUM": "中级", "HARD": "高级"}

DR_GRADE_TEXT = {
    "0": "0 级 无 DR",
    "1": "1 级 轻度 NPDR",
    "2": "2 级 中度 NPDR",
    "3": "3 级 重度 NPDR",
    "4": "4 级 PDR（增殖性）",
}


# ====================== 工具函数 ======================

def _flatten_images(image_paths: Optional[dict]) -> List[str]:
    """已迁移到 app.common.case_utils.flatten_image_paths（保留旧名以兼容本文件其他引用）"""
    from app.common.case_utils import flatten_image_paths
    return flatten_image_paths(image_paths)


def _bbox_of(points: List[Point2D]) -> Optional[Tuple[float, float, float, float]]:
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


def _gold_to_annotations(case: TrainingCase) -> List[PracticeAnnotation]:
    """把 case.gold_annotations JSON 转成统一的 PracticeAnnotation 结构"""
    raw = case.gold_annotations or []
    out: List[PracticeAnnotation] = []
    if not isinstance(raw, list):
        return out
    for idx, it in enumerate(raw):
        if not isinstance(it, dict):
            continue
        try:
            t = it.get("type") or it.get("tool") or "rect"
            label = it.get("label") or "微动脉瘤"

            if "points" in it and isinstance(it["points"], list):
                points = [
                    Point2D(x=float(p.get("x", 0)), y=float(p.get("y", 0)))
                    for p in it["points"] if isinstance(p, dict)
                ]
                tool = "rect" if t == "box" else (t if t in ("rect", "polygon", "pen") else "rect")
            else:
                x = float(it.get("x", 0))
                y = float(it.get("y", 0))
                w = float(it.get("w", 0))
                h = float(it.get("h", 0))
                points = [Point2D(x=x, y=y), Point2D(x=x + w, y=y + h)]
                tool = "rect"

            out.append(PracticeAnnotation(
                id=f"GOLD_{idx + 1}",
                tool=tool,
                points=points,
                label=label,
                color=it.get("color"),
                layer="gold",
                remark=it.get("remark", "") or "",
            ))
        except Exception:
            continue
    return out


# ====================== 评分核心 ======================

def _score(
    case: TrainingCase,
    student_dr_grade: str,
    student_diagnosis: str,
    student_anns: List[PracticeAnnotation],
) -> Tuple[dict, List[ErrorPoint]]:
    """
    自动比对评分
    - 分级题：DR 分级一致 → 100，否则相差等级越近分越高
    - 标注题：按 label 匹配最近金标准框，IoU 加权
    - 诊断书写：包含金标准关键词数 / 关键词总数（粗略匹配）
    """
    gold_anns = _gold_to_annotations(case)

    # ----- 1. 分级题 -----
    gold_dr = (case.gold_dr_grade or "0").strip()
    s_dr = (student_dr_grade or "").strip()
    grade_match = gold_dr == s_dr
    if grade_match:
        score_grade = 100.0
    else:
        try:
            diff = abs(int(gold_dr) - int(s_dr))
            score_grade = max(0.0, 100.0 - diff * 25.0)
        except Exception:
            score_grade = 0.0

    # ----- 2. 标注题 -----
    iou_threshold = 0.3
    error_points: List[ErrorPoint] = []
    iou_sum = 0.0
    iou_cnt = 0
    recall = 0
    used_g = set()

    for sa in student_anns:
        s_box = _bbox_of(sa.points)
        if not s_box:
            continue
        best_iou = 0.0
        best_idx = -1
        best_label = None
        for gi, ga in enumerate(gold_anns):
            if gi in used_g:
                continue
            g_box = _bbox_of(ga.points)
            if not g_box:
                continue
            v = _iou_box(s_box, g_box)
            if v > best_iou:
                best_iou = v
                best_idx = gi
                best_label = ga.label
        iou_sum += best_iou
        iou_cnt += 1
        if best_iou >= iou_threshold and best_idx >= 0:
            used_g.add(best_idx)
            recall += 1
            if sa.label != best_label:
                # 框对了但分类错了
                error_points.append(ErrorPoint(
                    type="wrong_label",
                    label=sa.label,
                    expected_label=best_label,
                    iou=round(best_iou, 4),
                    point=sa.points[0] if sa.points else None,
                    note=f"标注框命中但分类错误：你标为「{sa.label}」，金标准为「{best_label}」",
                ))
            elif best_iou < 0.5:
                error_points.append(ErrorPoint(
                    type="low_iou",
                    label=sa.label,
                    iou=round(best_iou, 4),
                    point=sa.points[0] if sa.points else None,
                    note=f"标注框定位偏差较大（IoU={best_iou:.2f}），建议提高定位精度",
                ))
        else:
            # 误诊（学员标了一个不存在的病灶）
            error_points.append(ErrorPoint(
                type="false_positive",
                label=sa.label,
                point=sa.points[0] if sa.points else None,
                note=f"误诊：金标准在该位置无「{sa.label}」病灶",
            ))

    # 漏诊
    for gi, ga in enumerate(gold_anns):
        if gi in used_g:
            continue
        error_points.append(ErrorPoint(
            type="missed",
            label=ga.label,
            expected_label=ga.label,
            point=ga.points[0] if ga.points else None,
            note=f"漏诊：未标注金标准中的「{ga.label}」",
        ))

    iou_avg = (iou_sum / iou_cnt) if iou_cnt else 0.0
    accuracy = (recall / len(gold_anns)) if gold_anns else (1.0 if not student_anns else 0.0)

    # 标注得分：召回率 70% + 平均 IoU 30%
    score_annotation = round(accuracy * 70.0 + iou_avg * 30.0, 2)

    # ----- 3. 诊断书写 -----
    keywords: List[str] = []
    if case.gold_diagnosis:
        for kw in case.gold_diagnosis.split():
            if len(kw) >= 2:
                keywords.append(kw)
    if not keywords:
        keywords = [DR_GRADE_TEXT.get(gold_dr, "").split(" ", 1)[-1] or "无 DR"]

    if student_diagnosis:
        hit = sum(1 for kw in keywords if kw and kw in student_diagnosis)
        score_diagnosis = round(min(100.0, hit / len(keywords) * 100.0), 2) if keywords else 60.0
        # 只要写了诊断起步给 30
        score_diagnosis = max(30.0, score_diagnosis)
    else:
        score_diagnosis = 0.0

    missed_cnt = sum(1 for e in error_points if e.type == "missed")
    fp_cnt = sum(1 for e in error_points if e.type == "false_positive")

    # ----- 总分加权 -----
    score_total = round(
        score_grade * 0.3 + score_annotation * 0.5 + score_diagnosis * 0.2,
        2,
    )

    pass_score = case.pass_score or 60
    is_passed = score_total >= pass_score

    # ----- 学习建议 -----
    tips: List[str] = []
    if not grade_match:
        tips.append(f"DR 分级与金标准不一致（应为 {DR_GRADE_TEXT.get(gold_dr, gold_dr)}）。")
    if iou_avg < 0.5 and iou_cnt > 0:
        tips.append("标注定位精度偏低，建议放大病灶后再勾画。")
    if missed_cnt > 0:
        tips.append(f"存在 {missed_cnt} 处漏诊，请重点关注金标准图层中标注的病灶。")
    if fp_cnt > 0:
        tips.append(f"存在 {fp_cnt} 处误诊，请结合 AI 热力图与教学要点核对。")
    if not student_diagnosis:
        tips.append("未填写诊断结论，建议结合分级与典型病变做规范化书写。")
    if not tips:
        tips.append("整体表现良好，继续保持规范化阅片习惯。")

    suggestion = " ".join(tips)

    return (
        {
            "score_total": score_total,
            "score_grade": score_grade,
            "score_annotation": score_annotation,
            "score_diagnosis": score_diagnosis,
            "iou_avg": round(iou_avg, 4),
            "accuracy": round(accuracy, 4),
            "missed_count": missed_cnt,
            "false_positive_count": fp_cnt,
            "grade_match": grade_match,
            "is_passed": is_passed,
            "suggestion": suggestion,
        },
        error_points,
    )


# ====================== 转换 ======================

def _to_out(record: PracticeSession) -> PracticeOut:
    case = record.case
    user = record.user
    teacher = record.teacher

    images = _flatten_images(case.image_paths) if case else []
    case_no = case.case_no if case else ""
    case_title = case.title if case else ""
    case_category = case.category if case else ""
    case_diff = case.difficulty if case else ""
    case_dr = (case.gold_dr_grade or "0") if case else "0"

    return PracticeOut(
        id=record.id,
        user_id=record.user_id,
        user_name=(user.real_name or user.username) if user else "",
        case_id=record.case_id,
        case_no=case_no,
        case_title=case_title,
        case_category=case_category,
        case_difficulty=case_diff,
        case_dr_grade_text=DR_GRADE_TEXT.get(case_dr, ""),
        images=images,
        mode=record.mode,  # type: ignore[arg-type]
        status=record.status,  # type: ignore[arg-type]
        student_dr_grade=record.student_dr_grade or "",
        student_diagnosis=record.student_diagnosis or "",
        student_annotations=record.student_annotations or [],
        student_measurements=record.student_measurements or [],
        viewport=record.viewport_snapshot,
        score_total=record.score_total or 0.0,
        score_grade=record.score_grade or 0.0,
        score_annotation=record.score_annotation or 0.0,
        score_diagnosis=record.score_diagnosis or 0.0,
        iou_avg=record.iou_avg or 0.0,
        accuracy=record.accuracy or 0.0,
        grade_match=bool(record.grade_match),
        is_passed=bool(record.is_passed),
        missed_count=record.missed_count or 0,
        false_positive_count=record.false_positive_count or 0,
        error_points=record.error_points or [],
        suggestion=record.suggestion or "",
        started_at=record.started_at,
        submitted_at=record.submitted_at,
        duration_seconds=record.duration_seconds or 0,
        teacher_comment=record.teacher_comment or "",
        teacher_id=record.teacher_id,
        teacher_name=(teacher.real_name or teacher.username) if teacher else "",
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _to_brief(case: TrainingCase) -> CaseBriefForPractice:
    images = _flatten_images(case.image_paths)
    dr = case.gold_dr_grade or "0"
    return CaseBriefForPractice(
        case_id=case.id,
        case_no=case.case_no,
        title=case.title or "",
        category=case.category,
        category_text=CATEGORY_TEXT.get(case.category, ""),
        difficulty=case.difficulty,
        difficulty_text=DIFFICULTY_TEXT.get(case.difficulty, ""),
        dr_level=int(dr) if dr.isdigit() else 0,
        dr_grade_text=DR_GRADE_TEXT.get(dr, ""),
        images=images,
        image_count=len(images),
        pass_score=case.pass_score or 60,
    )


# ====================== Service ======================

def _is_teacher_or_admin(user: User) -> bool:
    code = user.role.code if user.role else None
    return code in (RoleEnum.TEACHER.value, RoleEnum.ADMIN.value)


def _ensure_case_visible(case: TrainingCase, user: User) -> None:
    if _is_teacher_or_admin(user):
        return
    if (
        not case.is_published
        or case.archive_status == CaseArchiveStatusEnum.ARCHIVED.value
        or not bool(getattr(case, "is_train_case", False))
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="该病例尚未加入实训，学员暂不可练习",
        )


class PracticeService:

    # ---------- 病例抽取 ----------

    @staticmethod
    def random_case(db: Session, user: User, query: PracticeRandomQuery) -> CaseBriefForPractice:
        is_student = not _is_teacher_or_admin(user)

        q = db.query(TrainingCase).filter(
            TrainingCase.is_published == True,  # noqa: E712
            TrainingCase.archive_status == CaseArchiveStatusEnum.ACTIVE.value,
        )
        # 学员只看已加入实训的病例（教师/管理员看全部已发布）
        if is_student:
            q = q.filter(TrainingCase.is_train_case == True)  # noqa: E712

        if query.category:
            q = q.filter(TrainingCase.category == query.category)
        if query.difficulty:
            q = q.filter(TrainingCase.difficulty == query.difficulty)
        if query.dr_level is not None:
            q = q.filter(TrainingCase.gold_dr_grade == str(query.dr_level))

        if query.exclude_done:
            done_ids = (
                db.query(PracticeSession.case_id)
                .filter(
                    PracticeSession.user_id == user.id,
                    PracticeSession.status == PracticeStatusEnum.SUBMITTED.value,
                    PracticeSession.is_passed == 1,
                )
                .all()
            )
            done_set = {row[0] for row in done_ids}
            if done_set:
                q = q.filter(~TrainingCase.id.in_(done_set))

        cases: List[TrainingCase] = q.all()
        if not cases:
            # 兜底放宽：去掉 exclude_done，但仍保持「学员=实训库内」约束
            fallback = db.query(TrainingCase).filter(
                TrainingCase.is_published == True,  # noqa: E712
                TrainingCase.archive_status == CaseArchiveStatusEnum.ACTIVE.value,
            )
            if is_student:
                fallback = fallback.filter(TrainingCase.is_train_case == True)  # noqa: E712
            cases = fallback.all()
        if not cases:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "实训库暂无可用病例，请联系带教医师将病例加入实训"
                    if is_student
                    else "暂无可用练习病例，请先创建并发布病例"
                ),
            )

        shuffle(cases)
        return _to_brief(cases[0])

    @staticmethod
    def case_brief(db: Session, user: User, case_id: int) -> CaseBriefForPractice:
        case = db.query(TrainingCase).filter(TrainingCase.id == case_id).first()
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"病例不存在：{case_id}",
            )
        _ensure_case_visible(case, user)
        return _to_brief(case)

    # ---------- 金标准 ----------

    @staticmethod
    def get_gold_standard(db: Session, user: User, case_id: int) -> GoldStandardData:
        """提交后才允许查看金标准（防止学员"偷看"）"""
        case = db.query(TrainingCase).filter(TrainingCase.id == case_id).first()
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"病例不存在：{case_id}",
            )
        _ensure_case_visible(case, user)

        if not _is_teacher_or_admin(user):
            # 学员需要至少有一次该病例的提交记录
            submitted = (
                db.query(PracticeSession.id)
                .filter(
                    PracticeSession.user_id == user.id,
                    PracticeSession.case_id == case_id,
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

        dr = case.gold_dr_grade or "0"
        return GoldStandardData(
            case_id=case.id,
            case_no=case.case_no,
            dr_grade=dr,
            dr_grade_text=DR_GRADE_TEXT.get(dr, ""),
            diagnosis=case.gold_diagnosis or "",
            teaching_points=case.teaching_points or "",
            annotations=_gold_to_annotations(case),
            lesions=case.gold_lesions or [],
            pass_score=case.pass_score or 60,
        )

    # ---------- 开始练习 ----------

    @staticmethod
    def start(db: Session, user: User, params: PracticeStartParams) -> PracticeOut:
        case = db.query(TrainingCase).filter(TrainingCase.id == params.case_id).first()
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"病例不存在：{params.case_id}",
            )
        _ensure_case_visible(case, user)

        # 复用同一用户 + 同一病例的最近 DRAFT；否则新建
        record: Optional[PracticeSession] = (
            db.query(PracticeSession)
            .filter(
                PracticeSession.user_id == user.id,
                PracticeSession.case_id == case.id,
                PracticeSession.status == PracticeStatusEnum.DRAFT.value,
            )
            .order_by(desc(PracticeSession.id))
            .first()
        )
        if record is None:
            record = PracticeSession(
                user_id=user.id,
                case_id=case.id,
                mode=params.mode,
                status=PracticeStatusEnum.DRAFT.value,
                started_at=datetime.now(),
            )
            db.add(record)
            db.commit()
            db.refresh(record)
        else:
            record.mode = params.mode
            if not record.started_at:
                record.started_at = datetime.now()
            db.commit()
            db.refresh(record)

        return _to_out(record)

    # ---------- 提交（自动评分） ----------

    @staticmethod
    def submit(db: Session, user: User, params: PracticeSubmitParams) -> PracticeOut:
        record: Optional[PracticeSession] = (
            db.query(PracticeSession)
            .filter(PracticeSession.id == params.session_id)
            .first()
        )
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"练习会话不存在：{params.session_id}",
            )
        if record.user_id != user.id and not _is_teacher_or_admin(user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权操作他人练习会话",
            )
        if record.status != PracticeStatusEnum.DRAFT.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该练习会话已提交，无法重复提交",
            )

        case = record.case
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="练习关联的病例已被删除",
            )

        # 评分
        result, error_points = _score(
            case=case,
            student_dr_grade=params.student_dr_grade,
            student_diagnosis=params.student_diagnosis,
            student_anns=params.annotations,
        )

        # 落库
        record.student_dr_grade = params.student_dr_grade or ""
        record.student_diagnosis = params.student_diagnosis or ""
        record.student_annotations = [a.model_dump(by_alias=False) for a in params.annotations]
        record.student_measurements = [m.model_dump(by_alias=False) for m in params.measurements]
        record.viewport_snapshot = params.viewport
        record.duration_seconds = params.duration_seconds or 0
        record.submitted_at = datetime.now()
        record.status = PracticeStatusEnum.SUBMITTED.value

        record.score_total = result["score_total"]
        record.score_grade = result["score_grade"]
        record.score_annotation = result["score_annotation"]
        record.score_diagnosis = result["score_diagnosis"]
        record.iou_avg = result["iou_avg"]
        record.accuracy = result["accuracy"]
        record.missed_count = result["missed_count"]
        record.false_positive_count = result["false_positive_count"]
        record.grade_match = 1 if result["grade_match"] else 0
        record.is_passed = 1 if result["is_passed"] else 0
        record.error_points = [e.model_dump(by_alias=False) for e in error_points]
        record.suggestion = result["suggestion"]
        record.updated_at = datetime.now()

        db.commit()
        db.refresh(record)
        return _to_out(record)

    # ---------- 教师点评 ----------

    @staticmethod
    def review(
        db: Session,
        user: User,
        record_id: int,
        params: PracticeReviewParams,
    ) -> PracticeOut:
        if not _is_teacher_or_admin(user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="仅带教医师 / 管理员可点评",
            )
        record = (
            db.query(PracticeSession)
            .filter(PracticeSession.id == record_id)
            .first()
        )
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"练习记录不存在：{record_id}",
            )
        if record.status == PracticeStatusEnum.DRAFT.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该练习尚未提交，无法点评",
            )
        record.teacher_comment = params.teacher_comment or ""
        record.teacher_id = user.id
        record.status = PracticeStatusEnum.REVIEWED.value
        record.updated_at = datetime.now()
        db.commit()
        db.refresh(record)
        return _to_out(record)

    # ---------- 列表与详情 ----------

    @staticmethod
    def list_records(db: Session, user: User, query: PracticeListQuery) -> PracticePage:
        q = db.query(PracticeSession)

        # 权限范围
        if _is_teacher_or_admin(user):
            if query.user_id is not None:
                q = q.filter(PracticeSession.user_id == query.user_id)
        else:
            q = q.filter(PracticeSession.user_id == user.id)

        if query.case_id is not None:
            q = q.filter(PracticeSession.case_id == query.case_id)
        if query.status:
            q = q.filter(PracticeSession.status == query.status)
        if query.is_passed is not None:
            q = q.filter(PracticeSession.is_passed == (1 if query.is_passed else 0))
        if query.start_time:
            q = q.filter(PracticeSession.created_at >= query.start_time)
        if query.end_time:
            q = q.filter(PracticeSession.created_at <= query.end_time)

        total = q.count()
        rows = (
            q.order_by(desc(PracticeSession.id))
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
            .all()
        )
        return PracticePage(
            total=total,
            page=query.page,
            page_size=query.page_size,
            list=[_to_out(r) for r in rows],
        )

    @staticmethod
    def get_detail(db: Session, user: User, record_id: int) -> PracticeOut:
        record = (
            db.query(PracticeSession)
            .filter(PracticeSession.id == record_id)
            .first()
        )
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"练习记录不存在：{record_id}",
            )
        if not _is_teacher_or_admin(user) and record.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权查看该记录",
            )
        return _to_out(record)

    # ---------- 个人 / 班级统计 ----------

    @staticmethod
    def stats(db: Session, user: User, target_user_id: Optional[int] = None) -> PracticeStats:
        if target_user_id is None:
            uid = user.id
        else:
            if not _is_teacher_or_admin(user):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="无权查看他人统计",
                )
            uid = target_user_id

        if uid == 0 and _is_teacher_or_admin(user):
            # uid=0 + 教师/管理员：全局统计
            base = db.query(PracticeSession)
        else:
            base = db.query(PracticeSession).filter(PracticeSession.user_id == uid)

        total = base.count()
        submitted = base.filter(
            PracticeSession.status.in_([
                PracticeStatusEnum.SUBMITTED.value,
                PracticeStatusEnum.REVIEWED.value,
            ])
        ).count()
        passed = base.filter(PracticeSession.is_passed == 1).count()
        avg_score = (
            base.filter(
                PracticeSession.status.in_([
                    PracticeStatusEnum.SUBMITTED.value,
                    PracticeStatusEnum.REVIEWED.value,
                ])
            )
            .with_entities(func.avg(PracticeSession.score_total))
            .scalar()
        )
        avg_iou = (
            base.filter(
                PracticeSession.status.in_([
                    PracticeStatusEnum.SUBMITTED.value,
                    PracticeStatusEnum.REVIEWED.value,
                ])
            )
            .with_entities(func.avg(PracticeSession.iou_avg))
            .scalar()
        )
        total_dur = (
            base.with_entities(func.coalesce(func.sum(PracticeSession.duration_seconds), 0))
            .scalar()
        ) or 0

        # 薄弱知识点：聚合 error_points 中各 label 的次数
        rows = base.filter(
            PracticeSession.status.in_([
                PracticeStatusEnum.SUBMITTED.value,
                PracticeStatusEnum.REVIEWED.value,
            ])
        ).all()

        weak_map: dict = {}
        diff_map: dict = {}
        for r in rows:
            ep = r.error_points or []
            if isinstance(ep, list):
                for e in ep:
                    if not isinstance(e, dict):
                        continue
                    label = e.get("label") or e.get("expectedLabel") or "未知"
                    item = weak_map.setdefault(
                        label, {"label": label, "missed": 0, "false_positive": 0, "iou_sum": 0.0, "iou_cnt": 0}
                    )
                    typ = e.get("type") or ""
                    if typ == "missed":
                        item["missed"] += 1
                    elif typ == "false_positive":
                        item["false_positive"] += 1
                    iou_v = e.get("iou")
                    if isinstance(iou_v, (int, float)):
                        item["iou_sum"] += iou_v
                        item["iou_cnt"] += 1

            if r.case is not None:
                key = r.case.difficulty
                diff_map[key] = diff_map.get(key, 0) + 1

        weak_labels: List[WeakLabelItem] = []
        for v in weak_map.values():
            avg_iou_label = (v["iou_sum"] / v["iou_cnt"]) if v["iou_cnt"] else 0.0
            weak_labels.append(WeakLabelItem(
                label=v["label"],
                missed=v["missed"],
                false_positive=v["false_positive"],
                avg_iou=round(avg_iou_label, 4),
            ))
        weak_labels.sort(key=lambda x: (x.missed + x.false_positive), reverse=True)

        by_difficulty = [
            {"label": DIFFICULTY_TEXT.get(k, k), "value": v}
            for k, v in diff_map.items()
        ]

        return PracticeStats(
            total_sessions=total,
            submitted_sessions=submitted,
            pass_rate=round((passed / submitted), 4) if submitted else 0.0,
            avg_score=round(float(avg_score or 0.0), 2),
            avg_iou=round(float(avg_iou or 0.0), 4),
            total_duration=int(total_dur),
            weak_labels=weak_labels[:8],
            by_difficulty=by_difficulty,
        )

    # ---------- 删除（学员只能删自己 DRAFT） ----------

    @staticmethod
    def delete(db: Session, user: User, record_id: int) -> None:
        record = (
            db.query(PracticeSession)
            .filter(PracticeSession.id == record_id)
            .first()
        )
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"练习记录不存在：{record_id}",
            )
        is_self = record.user_id == user.id
        is_admin = (user.role.code if user.role else "") == RoleEnum.ADMIN.value
        if not (is_admin or (is_self and record.status == PracticeStatusEnum.DRAFT.value)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="仅可删除本人草稿，或由管理员删除",
            )
        db.delete(record)
        db.commit()
