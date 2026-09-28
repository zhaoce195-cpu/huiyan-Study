"""
学员自主练习业务层
- 病例随机抽取 / 指定病例
- 金标准查询
- 自主标注 → 提交后自动评分（IoU 比对 + 分级一致性 + 诊断匹配）
- 错误点位 / 漏诊 / 误诊 / 学习建议
- 个人台账 / 教师统计
"""

import re
import uuid
from datetime import datetime
from random import shuffle
from typing import List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import desc
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
from app.db.models.user import actor_role_text
from app.common import workflow
from app.common.dr_grade import grade_level, grade_text, is_applicable
from app.core.content_policy import Scene, redact, resolve_mode
from app.services.op_log_service import OpLogService
from app.services.common_service import learner_progress, learner_progress_sum
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

# 标注分算法当前版本。改公式时必须同步 +1，否则新旧分数混在一起
# 就再也分不清某个成绩是按哪套规则算出来的。已交卷的成绩不重算。
# 3：没有金标准框且学员也没标时，标注「未考」，不再记 100，权重摊给其余项。
# 4：文字题占 20%，分级 25%、标注 40%、诊断 15%。
# 5：病例学习。分级 40%、诊断 40%、文字题 20%。标注仍算出对照，不计入总分。
SCORE_RULE_VERSION = 5

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


def _is_finding_mark(ann) -> bool:
    """指出征象位置的标记。小病灶和象限征象计分时要算上，不再因为不是手绘框就丢掉。"""
    if isinstance(ann, dict):
        layer = ann.get("layer") or ""
        tool = ann.get("tool") or ""
    else:
        layer = getattr(ann, "layer", "") or ""
        tool = getattr(ann, "tool", "") or ""
    return layer == "finding" or tool in ("point", "quadrant")


_LESION_ALIAS = {
    "MA": "MA",
    "微动脉瘤": "MA",
    "微血管瘤": "MA",
    "HE": "HE",
    "出血": "HE",
    "EX": "EX",
    "硬性渗出": "EX",
    "渗出": "EX",
    "SE": "SE",
    "软性渗出": "SE",
    "棉绒斑": "SE",
    "VB": "VB",
    "静脉串珠": "VB",
    "IRMA": "IRMA",
    "视网膜内微血管异常": "IRMA",
    "NV": "NV",
    "NVD": "NV",
    "NVE": "NV",
    "新生血管": "NV",
}


def _lesion_code(label: str) -> str:
    text = (label or "").strip()
    if text in _LESION_ALIAS:
        return _LESION_ALIAS[text]
    head = text.split("·", 1)[0].strip()
    return _LESION_ALIAS.get(head, text)


def _is_small_span(box, canvas_w: float, canvas_h: float) -> bool:
    """边界只有几十像素的病灶，手画很难和金标准面积重合。"""
    span = max(box[2] - box[0], box[3] - box[1])
    if span <= 48:
        return True
    longer = max(canvas_w, canvas_h, 0)
    return longer > 0 and span <= longer * 0.02


def _lesion_rule(label: str, box=None, canvas_w: float = 0, canvas_h: float = 0) -> str:
    """微动脉瘤等小病灶看找对与否；大片出血渗出看范围；串珠、IRMA、新生血管看象限。"""
    code = _lesion_code(label)
    if code in ("VB", "IRMA", "NV"):
        return "place"
    if code == "MA":
        return "small"
    if box and _is_small_span(box, canvas_w, canvas_h):
        return "small"
    return "range"


def _same_lesion(a: str, b: str) -> bool:
    return _lesion_code(a) == _lesion_code(b) and bool(_lesion_code(a))


def _center_of(box: Tuple[float, float, float, float]) -> Tuple[float, float]:
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)


def _quadrant(x: float, y: float, width: float, height: float, eye: str) -> str:
    if width <= 0 or height <= 0:
        return ""
    right = x >= width / 2
    lower = y >= height / 2
    if eye == "OD":
        if not lower and right:
            return "NS"
        if not lower and not right:
            return "TS"
        if lower and right:
            return "NI"
        return "TI"
    if eye == "OS":
        if not lower and not right:
            return "NS"
        if not lower and right:
            return "TS"
        if lower and not right:
            return "NI"
        return "TI"
    if not lower and not right:
        return "LU"
    if not lower and right:
        return "RU"
    if lower and not right:
        return "LD"
    return "RD"


def _eye_for_place(ann, box, width: float, height: float, fallback: str) -> str:
    """象限标记本身带着鼻颞侧代码。用落点反推当时看的是哪只眼，避免左右眼把颞侧和鼻侧对调。"""
    remark = ""
    if isinstance(ann, dict):
        remark = ann.get("remark") or ""
    else:
        remark = getattr(ann, "remark", "") or ""
    code = ""
    if ":" in remark:
        code = remark.split(":", 1)[1].strip().upper()
    if code in ("LU", "RU", "LD", "RD") or width <= 0 or height <= 0:
        return ""
    if code not in ("TS", "NS", "TI", "NI"):
        return fallback if fallback in ("OD", "OS") else ""
    cx, cy = _center_of(box)
    as_od = _quadrant(cx, cy, width, height, "OD")
    as_os = _quadrant(cx, cy, width, height, "OS")
    if code == as_od and code != as_os:
        return "OD"
    if code == as_os and code != as_od:
        return "OS"
    return fallback if fallback in ("OD", "OS") else ""


def _mark_quadrant(ann, box, width: float, height: float, eye: str) -> str:
    remark = ""
    if isinstance(ann, dict):
        remark = ann.get("remark") or ""
    else:
        remark = getattr(ann, "remark", "") or ""
    if ":" in remark:
        code = remark.split(":", 1)[1].strip().upper()
        if code in ("TS", "NS", "TI", "NI", "LU", "RU", "LD", "RD"):
            return code
    cx, cy = _center_of(box)
    return _quadrant(cx, cy, width, height, eye)


def _small_hit(student_box, gold_box) -> bool:
    """点到或圈到附近就算找对，不要求边界重合。"""
    if _iou_box(student_box, gold_box) > 0:
        return True
    sx, sy = _center_of(student_box)
    gx, gy = _center_of(gold_box)
    span = max(gold_box[2] - gold_box[0], gold_box[3] - gold_box[1], 1.0)
    margin = max(28.0, span * 1.5)
    return (sx - gx) ** 2 + (sy - gy) ** 2 <= margin ** 2


def _range_credit(student_box, gold_box) -> float:
    """范围接近即可。0.45 的重叠视为这一处已经接近，不必完全重合。"""
    iou = _iou_box(student_box, gold_box)
    if iou < 0.2:
        return 0.0
    return min(1.0, iou / 0.45)


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


def _fundus_frame(db: Session, case: TrainingCase) -> Tuple[Tuple[int, int], str]:
    """象限要按真实画幅和眼别切。只有一只眼有图时眼别才明确，双眼病例改由落点反推。"""
    from app.db.models.case_image import CaseImage

    size = (0, 0)
    case_id = getattr(case, "id", None)
    if case_id:
        rows = (
            db.query(CaseImage)
            .filter(CaseImage.case_table == "training", CaseImage.case_id == case_id)
            .order_by(CaseImage.sort_order.asc(), CaseImage.id.asc())
            .all()
        )
        originals = [
            row for row in rows
            if row.role == "original" and (row.width or 0) > 0 and (row.height or 0) > 0
        ]
        sized = originals or [
            row for row in rows if (row.width or 0) > 0 and (row.height or 0) > 0
        ]
        if sized:
            size = (int(sized[0].width), int(sized[0].height))
    paths = getattr(case, "image_paths", None)
    eyes: List[str] = []
    if isinstance(paths, dict):
        for side in ("OD", "OS"):
            arr = paths.get(side) or []
            if isinstance(arr, list) and any(isinstance(url, str) and url for url in arr):
                eyes.append(side)
    eye = eyes[0] if len(eyes) == 1 else ""
    return size, eye


def _lesion_mask_url(db: Session, case_id: int) -> str:
    """彩色病灶图优先，其次叠加图。没有就返回空，调用方要如实说「没有」。"""
    from app.db.models.case_image import CaseImage

    rows = (
        db.query(CaseImage)
        .filter(
            CaseImage.case_table == "training",
            CaseImage.case_id == case_id,
            CaseImage.role.in_(["color_mask", "overlay"]),
        )
        .all()
    )
    by_role = {
        r.role: r.file_url
        for r in rows
        if (r.file_size or 0) >= 500 and r.file_url
    }
    return by_role.get("color_mask") or by_role.get("overlay") or ""


# ====================== 评分核心 ======================

def _score(
    case: TrainingCase,
    student_dr_grade: str,
    student_diagnosis: str,
    student_anns: List[PracticeAnnotation],
    structured: Optional[dict] = None,
    text_ids: Optional[List[str]] = None,
    text_values: Optional[dict] = None,
    image_size: Tuple[int, int] = (0, 0),
    eye: str = "",
) -> Tuple[dict, List[ErrorPoint]]:
    """
    自动比对评分
    - 分级题：DR 分级一致 → 100，否则相差等级越近分越高
    - 标注题：小病灶看找对、漏标、多标；出血和渗出看范围是否接近；
      静脉串珠、IRMA、新生血管看象限
    - 诊断书写：包含金标准关键词数 / 关键词总数（粗略匹配）
    """
    gold_anns = _gold_to_annotations(case)

    # ----- 1. 分级题 -----
    # 空的金标准分级表示「DR 分级不适用」（青光眼 / AMD 等非 DR 病种）。
    # 这类病例不该考分级题，否则学员无论答什么都会被扣分（报告 P1）。
    gold_dr = (case.gold_dr_grade or "").strip()
    grade_applicable = is_applicable(gold_dr)
    s_dr = (student_dr_grade or "").strip()

    if not grade_applicable:
        grade_match = True          # 不计入对错
        score_grade = 0.0           # 不计分，权重后续重新分配
    else:
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
    error_points: List[ErrorPoint] = []
    canvas_w, canvas_h = image_size
    if canvas_w <= 0 or canvas_h <= 0:
        xs: List[float] = []
        ys: List[float] = []
        for ann in list(gold_anns) + list(student_anns):
            box = _bbox_of(ann.points)
            if not box:
                continue
            xs.extend((box[0], box[2]))
            ys.extend((box[1], box[3]))
        canvas_w = max(xs) * 1.05 if xs else 0
        canvas_h = max(ys) * 1.05 if ys else 0

    drawable = []
    for sa in student_anns:
        if _bbox_of(sa.points):
            drawable.append(sa)
    used_s: set = set()
    used_g: set = set()
    credits: List[float] = []
    range_credits: List[float] = []
    # 同一处学生标记只对应一处金标准。同等信用时取离病灶中心更近的，避免远处的点抢走近处的病灶。
    pairs = []
    for gi, ga in enumerate(gold_anns):
        g_box = _bbox_of(ga.points)
        if not g_box:
            continue
        rule = _lesion_rule(ga.label, g_box, canvas_w, canvas_h)
        for si, sa in enumerate(drawable):
            if not _same_lesion(sa.label, ga.label):
                continue
            s_box = _bbox_of(sa.points)
            if not s_box:
                continue
            if rule == "small":
                credit = 1.0 if _small_hit(s_box, g_box) else 0.0
            elif rule == "place":
                eye_used = _eye_for_place(sa, s_box, canvas_w, canvas_h, eye) or eye
                gold_quad = _mark_quadrant(ga, g_box, canvas_w, canvas_h, eye_used)
                student_quad = _mark_quadrant(sa, s_box, canvas_w, canvas_h, eye_used)
                credit = 1.0 if gold_quad and gold_quad == student_quad else 0.0
            else:
                credit = _range_credit(s_box, g_box)
            if credit <= 0:
                continue
            gx, gy = _center_of(g_box)
            sx, sy = _center_of(s_box)
            dist = (sx - gx) ** 2 + (sy - gy) ** 2
            pairs.append((credit, dist, gi, si, rule, ga))
    pairs.sort(key=lambda item: (-item[0], item[1], item[2], item[3]))
    for credit, _dist, gi, si, rule, ga in pairs:
        if gi in used_g or si in used_s:
            continue
        used_s.add(si)
        used_g.add(gi)
        credits.append(credit)
        if rule == "range":
            range_credits.append(credit)
            if credit < 0.7:
                error_points.append(ErrorPoint(
                    type="low_iou",
                    label=ga.label,
                    iou=round(credit, 4),
                    point=ga.points[0] if ga.points else None,
                    note=f"「{ga.label}」找到了，但标出的范围还不够接近",
                ))

    for gi, ga in enumerate(gold_anns):
        if gi in used_g or not _bbox_of(ga.points):
            continue
        error_points.append(ErrorPoint(
            type="missed",
            label=ga.label,
            expected_label=ga.label,
            point=ga.points[0] if ga.points else None,
            note=f"漏标：没有找对「{ga.label}」",
        ))

    for si, sa in enumerate(drawable):
        if si in used_s:
            continue
        error_points.append(ErrorPoint(
            type="false_positive",
            label=sa.label,
            point=sa.points[0] if sa.points else None,
            note=f"多标：这里并没有「{sa.label}」",
        ))

    has_gold_boxes = len(gold_anns) > 0
    student_drew = len(drawable) > 0
    annotation_applicable = has_gold_boxes or student_drew
    recall = len(credits)
    if has_gold_boxes:
        accuracy = recall / len(gold_anns)
    else:
        accuracy = 0.0
    fp_marks = len(drawable) - len(used_s)
    # 每一处金标准最多 1 分。小病灶和象限征象找对就是 1；
    # 出血、渗出按范围接近程度给 0 到 1。多标会把分母加大。
    if not annotation_applicable:
        score_annotation = 0.0
    else:
        denom = len(gold_anns) + fp_marks
        score_annotation = round(100.0 * sum(credits) / denom, 2) if denom else 0.0
    # 没有出血或渗出可比时，不把「框重合」记成 0。用 -1 表示这项不按重合。
    if range_credits:
        iou_avg = sum(range_credits) / len(range_credits)
    elif any(
        _lesion_rule(ga.label, _bbox_of(ga.points), canvas_w, canvas_h) == "range"
        for ga in gold_anns
        if _bbox_of(ga.points)
    ):
        iou_avg = 0.0
    else:
        iou_avg = -1.0

    # ----- 3. 诊断书写 -----
    keywords: List[str] = []
    if case.gold_diagnosis:
        for kw in case.gold_diagnosis.split():
            if len(kw) >= 2:
                keywords.append(kw)
    if not keywords:
        keywords = [DR_GRADE_TEXT.get(gold_dr, "").split(" ", 1)[-1] or "无 DR"]

    # 结构化作答优先：比关键词匹配可靠得多。
    # 关键词只看学员有没有写到某几个词，写法稍变就判错，
    # 也无法区分「征象对但处置错」。
    #
    # 两种口径不混用：有结构化作答就整题走结构化，否则沿用关键词，
    # 并由调用方把口径记进 scoring_mode，使历史成绩可解释、可对比。
    scoring_mode = "keyword"
    structured_errors: List[str] = []
    if structured:
        from app.common import diagnosis_form

        gold_struct = diagnosis_form.gold_from_case(case)
        result = diagnosis_form.score_structured(
            case.category, structured, gold_struct,
        )
        score_diagnosis = result["score"]
        structured_errors = result["errors"]
        scoring_mode = "structured"
    elif student_diagnosis:
        hit = sum(1 for kw in keywords if kw and kw in student_diagnosis)
        score_diagnosis = round(min(100.0, hit / len(keywords) * 100.0), 2) if keywords else 60.0
        # 只要写了诊断起步给 30
        score_diagnosis = max(30.0, score_diagnosis)
    else:
        score_diagnosis = 0.0

    missed_cnt = sum(1 for e in error_points if e.type == "missed")
    fp_cnt = sum(1 for e in error_points if e.type == "false_positive")

    # ----- 文字题 -----
    # 没有题号的是旧练习，不把文字题算进总分，权重仍是分级 30 / 标注 50 / 诊断 20。
    # 新练习在点「开始练习」时就定下一组题，没写的按错，占总分 20%。
    from app.services.text_quiz import BY_ID, grade_answers

    bound_ids = [qid for qid in (text_ids or []) if qid in BY_ID]
    text_applicable = bool(bound_ids)
    text_values = text_values or {}
    if text_applicable:
        graded_text = grade_answers([(qid, str(text_values.get(qid, ""))) for qid in bound_ids])
        score_text = float(graded_text["score"])
        text_hit = (
            graded_text["correct_count"],
            graded_text["question_count"],
        )
    else:
        score_text = 0.0
        text_hit = None

    # ----- 总分加权 -----
    # 有文字题的新练习（版本 5）：分级 40% + 诊断 40% + 文字题 20%。
    # 标注对照仍计算，但不计入总分。临床学习看的是这例的结论，不是画框。
    # 没有文字题的旧卷：分级 30% + 标注 50% + 诊断 20%。已交卷的不重算。
    # 某一项未考时，把它的权重摊给仍在考的项，满分仍是 100。
    if text_applicable:
        w_grade, w_ann, w_diag, w_text = 0.40, 0.0, 0.40, 0.20
    else:
        w_grade, w_ann, w_diag, w_text = 0.30, 0.50, 0.20, 0.0
    parts: List[Tuple[float, float]] = []
    if grade_applicable:
        parts.append((score_grade, w_grade))
    if annotation_applicable and w_ann > 0:
        parts.append((score_annotation, w_ann))
    parts.append((score_diagnosis, w_diag))
    if text_applicable:
        parts.append((score_text, w_text))
    weight_sum = sum(w for _, w in parts)
    score_total = round(
        sum(s * w for s, w in parts) / weight_sum, 2,
    ) if weight_sum else 0.0

    pass_score = case.pass_score or 60
    is_passed = score_total >= pass_score

    # ----- 学习建议 -----
    tips: List[str] = []
    if grade_applicable and not grade_match:
        tips.append(f"DR 分级与这例的标准结论不一致（应为 {DR_GRADE_TEXT.get(gold_dr, gold_dr)}）。")
    for msg in structured_errors:
        tips.append(msg)
    if scoring_mode == "keyword" and not student_diagnosis:
        tips.append("还没有写下这例的诊断。")
    if text_hit and text_hit[0] < text_hit[1]:
        tips.append(f"文字题答对 {text_hit[0]}/{text_hit[1]}，已计入总分。")
    if not text_applicable:
        if range_credits and sum(range_credits) / len(range_credits) < 0.7:
            tips.append("出血或渗出已经找到，但标出的范围还不够接近。")
        if not annotation_applicable:
            tips.append("本病例没有金标准标注框，标注不计入成绩，没画框也不会记成 100 分。")
        if missed_cnt > 0:
            tips.append(f"存在 {missed_cnt} 处漏诊，请重点关注金标准图层中标注的病灶。")
        if fp_cnt > 0:
            tips.append(f"存在 {fp_cnt} 处误诊，请结合 AI 热力图与教学要点核对。")
        if not tips:
            tips.append("整体表现良好，继续保持规范化阅片习惯。")
    elif not tips:
        if grade_applicable:
            tips.append("这例的分级和诊断都对上了。交卷后可以打开标准结论，再看病灶在哪里。")
        else:
            tips.append("这例不考 DR 分级。交卷后可以打开标准结论，再看诊断是否对上。")

    suggestion = " ".join(tips)

    return (
        {
            "scoring_mode": scoring_mode,
            "structured_errors": structured_errors,
            "score_total": score_total,
            "score_grade": score_grade,
            "score_annotation": score_annotation,
            "annotation_applicable": annotation_applicable,
            "score_diagnosis": score_diagnosis,
            "score_text": score_text,
            "text_applicable": text_applicable,
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

def _question_ids(record: PracticeSession) -> list:
    raw = record.text_question_ids or []
    if isinstance(raw, str):
        import json
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            return []
    return list(raw) if isinstance(raw, list) else []


def _ensure_text_paper(record: PracticeSession) -> bool:
    """开始练习时定下一组文字题。已有题号就不再换，避免刷新后题目变了。"""
    if _question_ids(record):
        return False
    from app.services.text_quiz import build_paper
    record.text_question_ids = [item.id for item in build_paper(4)]
    return True


def _text_questions(record: PracticeSession) -> list:
    from app.services.text_quiz import BY_ID, public_question
    out = []
    for qid in _question_ids(record):
        item = BY_ID.get(qid)
        if item is None:
            continue
        face = public_question(item)
        out.append({
            "id": face["id"],
            "kind": face["kind"],
            "kindText": face["kind_text"],
            "stem": face["stem"],
            "options": face["options"],
        })
    return out


def _text_items(record: PracticeSession) -> list:
    from app.services.text_quiz import BY_ID, KIND_TEXT, is_correct
    answers = {}
    for row in record.text_answers or []:
        if isinstance(row, dict) and row.get("id"):
            answers[row["id"]] = row.get("value") or ""
    items = []
    for qid in _question_ids(record):
        item = BY_ID.get(qid)
        if item is None:
            continue
        value = answers.get(qid, "")
        items.append({
            "id": item.id,
            "kind": item.kind,
            "kindText": KIND_TEXT[item.kind],
            "stem": item.stem,
            "yours": value,
            "expected": item.answer,
            "correct": is_correct(item, value),
            "explanation": item.explanation,
        })
    return items


EXAM_PAPER_SIZE = 3


def _is_exam(record: PracticeSession) -> bool:
    return (record.attempt_kind or "PRACTICE") == "EXAM"


def _answers_open(db: Session, record: PracticeSession) -> bool:
    """平时练习交卷即开放答案。正式考试要同一场全部交卷。"""
    done = record.status in (
        PracticeStatusEnum.SUBMITTED.value,
        PracticeStatusEnum.REVIEWED.value,
    )
    if not _is_exam(record):
        return done
    # 老师发布的考试要等收卷，避免先交卷的学员把答案传给还在考的人。
    if int(getattr(record, "exam_paper_id", 0) or 0):
        from app.services.exam_service import answers_locked_by_paper
        if answers_locked_by_paper(db, record):
            return False
    group_id = (record.exam_group_id or "").strip()
    if not group_id:
        return done
    pending = (
        db.query(PracticeSession.id)
        .filter(
            PracticeSession.exam_group_id == group_id,
            PracticeSession.status == PracticeStatusEnum.DRAFT.value,
        )
        .first()
    )
    return pending is None


def exam_locks_answers(db: Session, user_id: int, case_id: int) -> bool:
    """这名学员有一场还没交完、并且包含该病例的考试。"""
    rows = (
        db.query(PracticeSession)
        .filter(
            PracticeSession.user_id == user_id,
            PracticeSession.case_id == case_id,
            PracticeSession.attempt_kind == "EXAM",
        )
        .all()
    )
    return any(not _answers_open(db, row) for row in rows)


def _hint_catalog(record: PracticeSession, case: Optional[TrainingCase]) -> List[str]:
    """平时练习的提示阶梯。不含标准分级、金标准框和文字题标准答案。"""
    from app.services.text_quiz import BY_ID

    lines = [
        "先确认眼别和图像是否清楚，再看视盘、血管和黄斑，把出血、渗出、微动脉瘤分开记。",
    ]
    raw = (case.teaching_points or "").strip() if case else ""
    if raw:
        parts = [
            part.strip()
            for part in re.split(r"[\n；;。]", raw)
            if len(part.strip()) >= 4
        ]
        for part in parts[:2]:
            lines.append(part[:160])
    for qid in _question_ids(record):
        item = BY_ID.get(qid)
        if item and item.explanation:
            lines.append(item.explanation)
    return lines[:6]


def _next_exam_item(db: Session, record: PracticeSession) -> Tuple[int, int]:
    if not _is_exam(record) or not (record.exam_group_id or "").strip():
        return 0, 0
    nxt = (
        db.query(PracticeSession)
        .filter(
            PracticeSession.exam_group_id == record.exam_group_id,
            PracticeSession.status == PracticeStatusEnum.DRAFT.value,
            PracticeSession.id != record.id,
        )
        .order_by(PracticeSession.exam_index.asc(), PracticeSession.id.asc())
        .first()
    )
    if nxt is None:
        return 0, 0
    return int(nxt.id), int(nxt.case_id)


def _to_out(record: PracticeSession, db: Session, viewer: Optional[User] = None) -> PracticeOut:
    case = record.case
    user = record.user
    teacher = record.teacher

    images = _flatten_images(case.image_paths) if case else []
    case_no = case.case_no if case else ""
    revealed = _answers_open(db, record)
    show_scores = revealed or (
        viewer is not None
        and _is_teacher_or_admin(viewer)
        and record.status in (
            PracticeStatusEnum.SUBMITTED.value,
            PracticeStatusEnum.REVIEWED.value,
        )
    )
    raw_title = case.title if case else ""
    case_title = raw_title if revealed else (f"病例 {case_no}" if case_no else "待判读病例")
    case_category = case.category if case else ""
    case_diff = case.difficulty if case else ""
    case_dr = (case.gold_dr_grade or "") if (case and revealed) else ""
    # 按病例当前的金标准框判断，不看当时存下来的标注分。
    # 旧记录可能把「没有框」存成 100，界面仍应显示「未考」。
    gold_boxes = _gold_to_annotations(case) if case else []
    student_marks = record.student_annotations or []
    # 新口径把点选和象限也算进标注。旧记录的 iou 不会是负数，仍按当时「手绘框才算标注」显示，不改已存分数。
    if (record.iou_avg or 0) < 0:
        scoring_marks = [
            m for m in student_marks
            if isinstance(m, dict) and m.get("points")
        ]
    else:
        scoring_marks = [m for m in student_marks if not _is_finding_mark(m)]
    annotation_applicable = bool(gold_boxes) or bool(scoring_marks)

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
        student_diagnosis_form=record.student_diagnosis_form or {},
        scoring_mode=record.scoring_mode or "keyword",
        score_rule_version=record.score_rule_version or 1,
        student_annotations=record.student_annotations or [],
        student_measurements=record.student_measurements or [],
        viewport=record.viewport_snapshot,
        score_total=(record.score_total or 0.0) if show_scores else 0.0,
        score_grade=(record.score_grade or 0.0) if show_scores else 0.0,
        score_annotation=(record.score_annotation or 0.0) if show_scores else 0.0,
        annotation_applicable=annotation_applicable,
        score_diagnosis=(record.score_diagnosis or 0.0) if show_scores else 0.0,
        score_text=(record.score_text or 0.0) if show_scores else 0.0,
        text_questions=_text_questions(record),
        text_items=_text_items(record) if revealed else [],
        iou_avg=(record.iou_avg or 0.0) if show_scores else 0.0,
        accuracy=(record.accuracy or 0.0) if show_scores else 0.0,
        grade_match=bool(record.grade_match) if show_scores else False,
        is_passed=bool(record.is_passed) if show_scores else False,
        missed_count=(record.missed_count or 0) if show_scores else 0,
        false_positive_count=(record.false_positive_count or 0) if show_scores else 0,
        error_points=(record.error_points or []) if show_scores else [],
        suggestion=(record.suggestion or "") if revealed else "",
        started_at=record.started_at,
        submitted_at=record.submitted_at,
        duration_seconds=record.duration_seconds or 0,
        teacher_comment=record.teacher_comment or "",
        teacher_id=record.teacher_id,
        teacher_name=(teacher.real_name or teacher.username) if teacher else "",
        teacher_role=actor_role_text(teacher) if teacher else "",
        created_at=record.created_at,
        updated_at=record.updated_at,
        attempt_kind=record.attempt_kind or "PRACTICE",
        exam_group_id=record.exam_group_id or "",
        exam_index=record.exam_index or 0,
        exam_total=record.exam_total or 0,
        answers_open=revealed,
        hints=(
            []
            if _is_exam(record)
            else _hint_catalog(record, case)[: int(record.hint_step or 0)]
        ),
        hints_left=(
            0
            if _is_exam(record) or revealed
            else max(0, len(_hint_catalog(record, case)) - int(record.hint_step or 0))
        ),
        **_exam_navigation(db, record),
    )


def _exam_navigation(db: Session, record: PracticeSession) -> dict:
    nxt = _next_exam_item(db, record)
    face = _exam_face(db, record)
    if face.get("allow_back"):
        following = next(
            (
                item for item in face.get("exam_items") or []
                if item.index == (record.exam_index or 0) + 1
            ),
            None,
        )
        nxt = (int(following.session_id), int(following.case_id)) if following else (0, 0)
    return {
        "next_session_id": nxt[0],
        "next_case_id": nxt[1],
        **face,
    }


def _exam_face(db: Session, record: PracticeSession) -> dict:
    if not int(getattr(record, "exam_paper_id", 0) or 0):
        return {}
    from app.services.exam_service import paper_face
    return paper_face(db, record)


def _has_answered(db: Session, user: User, case_id: int) -> bool:
    """该用户是否已对此病例提交过作答（盲态解除的唯一依据，服务端判定）"""
    return (
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
        is not None
    )


def _to_brief(case: TrainingCase, *, user: Optional[User] = None,
              answered: bool = False) -> CaseBriefForPractice:
    """
    练习病例摘要。

    盲训内容策略：开始练习的卡片不出现正确 DR 分级，标题里的分级也会换成病例号。
    以前是否交过卷不影响这张卡片；交卷后的评分报告才展示标准分级。
    """
    images = _flatten_images(case.image_paths)
    dr_raw = case.gold_dr_grade  # 空 = DR 分级不适用
    brief = CaseBriefForPractice(
        case_id=case.id,
        case_no=case.case_no,
        title=case.title or "",
        category=case.category,
        category_text=CATEGORY_TEXT.get(case.category, ""),
        difficulty=case.difficulty,
        difficulty_text=DIFFICULTY_TEXT.get(case.difficulty, ""),
        dr_level=grade_level(dr_raw),
        dr_grade_text=grade_text(dr_raw),
        images=images,
        image_count=len(images),
        pass_score=case.pass_score or 60,
    )

    mode = resolve_mode(
        viewer_role=user.role.code if (user and user.role) else None,
        scene=Scene.PRACTICE,
        answered=answered,
    )
    return CaseBriefForPractice(
        **redact(brief.model_dump(), mode, case_no=case.case_no)
    )


# ====================== Service ======================

def _is_teacher_or_admin(user: User) -> bool:
    code = user.role.code if user.role else None
    if code in (RoleEnum.TEACHER.value, RoleEnum.ADMIN.value):
        return True
    ut = (getattr(user, "user_type", "") or "").lower()
    return ut in ("teacher", "admin")


def _passback_to_lms(db: Session, user: User, record: PracticeSession) -> None:
    """
    把成绩回传到 LMS 的作业栏（LTI AGS）。

    失败不影响提交：成绩已经在本系统落库了，回传是集成问题，
    不该让学员的提交跟着失败。但结果必须记进审计 ——
    默默失败会让教师以为分数已经进作业栏了，
    等到期末对分才发现，那时已经无从追溯。
    """
    from app.db.models import LtiLaunch
    from app.services import lti_service

    launch = (
        db.query(LtiLaunch)
        .filter(LtiLaunch.user_id == user.id)
        .order_by(desc(LtiLaunch.id))
        .first()
    )
    if not launch:
        return
    try:
        result = lti_service.post_score(
            db, launch,
            score=float(record.score_total or 0),
            max_score=100.0,
            comment=f"练习 #{record.id}",
        )
    except Exception as exc:
        result = f"回传异常：{exc}"

    OpLogService.record(
        db, user=user, module="lti", action="score_passback",
        detail=f"练习会话 #{record.id} 成绩 {record.score_total} → {result}",
    )


def _replay_or_reject(db: Session, record: PracticeSession, request_id: str) -> PracticeOut:
    """
    会话已不是草稿时，判断这是「同一次提交的重试」还是「另一次提交」。

    断网重试是正常操作：请求到了服务端、成绩已落库，只是响应没回来。
    此时再报「已提交，无法重复提交」，学员看到的是一个失败提示，
    会以为答卷丢了——而实际上早就判完分了。所以同键必须回放原结果。

    异键才是真的重复提交（比如从两个标签页各答一遍），仍然拒绝：
    成绩已经产生，不允许覆盖。
    """
    if request_id and record.submit_request_id == request_id:
        return _to_out(record, db)
    # 不是重试就是真的重复提交。合法性交给状态机判，
    # 免得这里和状态机各写一套规则、日后改一处漏一处。
    workflow.PRACTICE.ensure(record.status, PracticeStatusEnum.SUBMITTED.value)
    return _to_out(record, db)


def _pick_across_grades(cases: List[TrainingCase], n: int) -> List[TrainingCase]:
    """抽卷时尽量让不同 DR 分级都出现，避免三题都落在重度。"""
    by_grade: dict = {}
    for case in cases:
        by_grade.setdefault(str(case.gold_dr_grade or ""), []).append(case)
    for group in by_grade.values():
        shuffle(group)
    grades = list(by_grade)
    shuffle(grades)
    picked: List[TrainingCase] = []
    while len(picked) < n and grades:
        still = []
        for grade in grades:
            bucket = by_grade[grade]
            if bucket and len(picked) < n:
                picked.append(bucket.pop())
            if bucket:
                still.append(grade)
        grades = still
    return picked


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
        picked = cases[0]
        return _to_brief(
            picked, user=user, answered=_has_answered(db, user, picked.id),
        )

    @staticmethod
    def case_brief(db: Session, user: User, case_id: int) -> CaseBriefForPractice:
        case = db.query(TrainingCase).filter(TrainingCase.id == case_id).first()
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"病例不存在：{case_id}",
            )
        _ensure_case_visible(case, user)
        return _to_brief(
            case, user=user, answered=_has_answered(db, user, case.id),
        )

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
            if exam_locks_answers(db, user.id, case_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="正式考试要全部交卷后才能查看金标准",
                )
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

        dr = (case.gold_dr_grade or "").strip()
        return GoldStandardData(
            case_id=case.id,
            case_no=case.case_no,
            dr_grade=dr,
            dr_grade_text=grade_text(dr),
            diagnosis=case.gold_diagnosis or "",
            teaching_points=case.teaching_points or "",
            annotations=_gold_to_annotations(case),
            lesions=case.gold_lesions or [],
            lesion_mask_url=_lesion_mask_url(db, case.id),
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
                PracticeSession.attempt_kind != "EXAM",
            )
            .order_by(desc(PracticeSession.id))
            .first()
        )
        if record is None:
            record = PracticeSession(
                user_id=user.id,
                case_id=case.id,
                mode=params.mode,
                attempt_kind="PRACTICE",
                status=PracticeStatusEnum.DRAFT.value,
                started_at=datetime.now(),
            )
            db.add(record)
        else:
            record.mode = params.mode
            if not record.started_at:
                record.started_at = datetime.now()
        _ensure_text_paper(record)
        db.commit()
        db.refresh(record)

        return _to_out(record, db)

    # ---------- 正式考试（多题，整卷交齐后才开放答案） ----------

    @staticmethod
    def start_exam(db: Session, user: User) -> PracticeOut:
        open_row = (
            db.query(PracticeSession)
            .filter(
                PracticeSession.user_id == user.id,
                PracticeSession.attempt_kind == "EXAM",
                PracticeSession.status == PracticeStatusEnum.DRAFT.value,
            )
            .order_by(PracticeSession.exam_index.asc(), PracticeSession.id.asc())
            .first()
        )
        if open_row is not None:
            return _to_out(open_row, db)

        cases = (
            db.query(TrainingCase)
            .filter(
                TrainingCase.is_published == True,  # noqa: E712
                TrainingCase.archive_status == CaseArchiveStatusEnum.ACTIVE.value,
            )
            .all()
        )
        visible: List[TrainingCase] = []
        for case in cases:
            try:
                _ensure_case_visible(case, user)
            except HTTPException:
                continue
            visible.append(case)
        picked = _pick_across_grades(visible, EXAM_PAPER_SIZE)
        if not picked:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="暂无可考试的病例，请联系带教医师将病例加入实训",
            )

        group_id = uuid.uuid4().hex
        total = len(picked)
        first: Optional[PracticeSession] = None
        for index, case in enumerate(picked, start=1):
            record = PracticeSession(
                user_id=user.id,
                case_id=case.id,
                mode=PracticeModeEnum.RANDOM.value,
                attempt_kind="EXAM",
                exam_group_id=group_id,
                exam_index=index,
                exam_total=total,
                status=PracticeStatusEnum.DRAFT.value,
                started_at=datetime.now(),
            )
            db.add(record)
            db.flush()
            _ensure_text_paper(record)
            if first is None:
                first = record
        db.commit()
        assert first is not None
        db.refresh(first)
        return _to_out(first, db)

    @staticmethod
    def next_hint(db: Session, user: User, record_id: int) -> PracticeOut:
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
        if record.user_id != user.id and not _is_teacher_or_admin(user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权查看该记录",
            )
        if _is_exam(record):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="正式考试不能查看提示，请交完全部题目后再看答案",
            )
        if record.status != PracticeStatusEnum.DRAFT.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="已经交卷，请直接看评分报告",
            )
        catalog = _hint_catalog(record, record.case)
        step = int(record.hint_step or 0)
        if step >= len(catalog):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="没有更多提示了",
            )
        record.hint_step = step + 1
        db.commit()
        db.refresh(record)
        return _to_out(record, db)

    # ---------- 提交（自动评分） ----------

    @staticmethod
    def submit(db: Session, user: User, params: PracticeSubmitParams, _clock: bool = True) -> PracticeOut:
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
            return _replay_or_reject(db, record, params.request_id)

        if _clock and int(record.exam_paper_id or 0):
            from app.services.exam_service import apply_draft, clock_expired, finalize_user
            if clock_expired(db, record):
                apply_draft(db, record, params)
                finalize_user(db, record.user_id, int(record.exam_paper_id))
                db.refresh(record)
                return _to_out(record, db)

        case = record.case
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="练习关联的病例已被删除",
            )

        if _clock and params.diagnosis:
            from app.common import diagnosis_form

            dme_problem = diagnosis_form.dme_answer_problem(
                params.diagnosis,
                diagnosis_form.materials_for_case(db, case),
            )
            if dme_problem:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=dme_problem,
                )

        # 评分
        if _ensure_text_paper(record):
            db.flush()
        text_values = {row.id: row.value for row in params.text_answers}
        image_size, eye = _fundus_frame(db, case)
        result, error_points = _score(
            case=case,
            student_dr_grade=params.student_dr_grade,
            student_diagnosis=params.student_diagnosis,
            student_anns=params.annotations,
            structured=params.diagnosis or None,
            text_ids=_question_ids(record),
            text_values=text_values,
            image_size=image_size,
            eye=eye,
        )

        # 抢占式置为已提交：WHERE status='DRAFT' 由数据库保证只有一个请求成功。
        # 防的是双击/重试同时在途——两个请求都读到 DRAFT 时，后者不能也写一遍。
        claimed = (
            db.query(PracticeSession)
            .filter(
                PracticeSession.id == record.id,
                PracticeSession.status == PracticeStatusEnum.DRAFT.value,
            )
            .update(
                {
                    PracticeSession.status: PracticeStatusEnum.SUBMITTED.value,
                    PracticeSession.submit_request_id: params.request_id or None,
                },
                synchronize_session=False,
            )
        )
        if not claimed:
            db.expire(record)
            return _replay_or_reject(db, record, params.request_id)

        # 落库
        record.student_dr_grade = params.student_dr_grade or ""
        record.student_diagnosis = params.student_diagnosis or ""
        record.student_annotations = [a.model_dump(by_alias=False) for a in params.annotations]
        record.student_measurements = [m.model_dump(by_alias=False) for m in params.measurements]
        record.viewport_snapshot = params.viewport
        record.duration_seconds = params.duration_seconds or 0
        record.submitted_at = datetime.now()
        record.status = PracticeStatusEnum.SUBMITTED.value

        record.student_diagnosis_form = params.diagnosis or None
        record.scoring_mode = result.get("scoring_mode", "keyword")
        record.score_rule_version = SCORE_RULE_VERSION if result.get("text_applicable") else 3
        record.score_total = result["score_total"]
        record.score_grade = result["score_grade"]
        record.score_annotation = result["score_annotation"]
        record.score_diagnosis = result["score_diagnosis"]
        record.score_text = result.get("score_text") or 0.0
        record.text_answers = [
            {"id": qid, "value": text_values.get(qid, "")}
            for qid in _question_ids(record)
        ]
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

        # 审计：谁、什么时候、提交了哪份答卷、按哪套口径判的多少分。
        # 成绩有争议时要能回溯，写在业务表之外，避免被后续操作覆盖。
        OpLogService.record(
            db,
            user=user,
            module="practice",
            action="submit",
            detail=workflow.transition_detail(
                workflow.PRACTICE, record.id,
                PracticeStatusEnum.DRAFT.value,
                PracticeStatusEnum.SUBMITTED.value,
                extra=(
                    f"病例 {record.case_id} 总分 {record.score_total} "
                    f"口径 {record.scoring_mode} "
                    f"{'通过' if record.is_passed else '未通过'} "
                    f"用时 {record.duration_seconds}s"
                ),
            ),
        )

        _passback_to_lms(db, user, record)
        return _to_out(record, db)

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
        before = record.status
        workflow.PRACTICE.ensure(before, PracticeStatusEnum.REVIEWED.value)
        record.teacher_comment = params.teacher_comment or ""
        record.teacher_id = user.id
        record.status = PracticeStatusEnum.REVIEWED.value
        record.updated_at = datetime.now()
        db.commit()
        db.refresh(record)

        OpLogService.record(
            db,
            user=user,
            module="practice",
            action="review",
            detail=workflow.transition_detail(
                workflow.PRACTICE, record.id,
                before, PracticeStatusEnum.REVIEWED.value,
                extra=f"学员 {record.user_id} 总分 {record.score_total}",
            ),
        )
        return _to_out(record, db, user)

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
            list=[_to_out(r, db, user) for r in rows],
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
        if record.status == PracticeStatusEnum.DRAFT.value and _ensure_text_paper(record):
            db.commit()
            db.refresh(record)
        if int(getattr(record, "exam_paper_id", 0) or 0):
            from app.services.exam_service import expire_if_needed, guard_back
            expire_if_needed(db, record)
            db.refresh(record)
            if not _is_teacher_or_admin(user):
                guard_back(db, record)
        return _to_out(record, db, user)

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
            progress = learner_progress_sum(learner_progress(db, None))
            base = db.query(PracticeSession)
        else:
            progress = learner_progress(db, [uid])[uid]
            base = db.query(PracticeSession).filter(PracticeSession.user_id == uid)

        total = base.count()
        submitted = progress["practice_count"]
        passed = progress["passed"]

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
            completed_cases=progress["completed_cases"],
            pass_rate=round((passed / submitted), 4) if submitted else 0.0,
            avg_score=progress["avg_score"],
            avg_iou=progress["avg_iou"],
            total_duration=progress["total_seconds"],
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
