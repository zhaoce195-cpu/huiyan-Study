"""老师组卷的正式考试。

抽题在发布时定稿，全班同一套。收卷前不公布答案。
学员自行开考的旧卷不走这里。
"""

import csv
import io
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import (
    CaseArchiveStatusEnum,
    ExamPaper,
    PracticeSession,
    PracticeStatusEnum,
    Role,
    RoleEnum,
    TrainingCase,
    User,
)
from app.schemas.exam import ExamCreate, ExamPaperOut, hand_in_as_submit
from app.schemas.practice import ExamNavItem, PracticeAnnotation, PracticeSubmitParams
from app.services.practice_service import (
    CATEGORY_TEXT,
    DIFFICULTY_TEXT,
    PracticeService,
    _is_teacher_or_admin,
    _pick_across_grades,
    _to_out,
)


def _require_teacher(user: User) -> None:
    if not _is_teacher_or_admin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有老师可以安排考试")


def _paper_or_404(db: Session, paper_id: int) -> ExamPaper:
    paper = db.query(ExamPaper).filter(ExamPaper.id == paper_id).first()
    if paper is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="考试不存在")
    return paper


def _pool(db: Session) -> List[TrainingCase]:
    return (
        db.query(TrainingCase)
        .filter(
            TrainingCase.is_published == True,  # noqa: E712
            TrainingCase.is_train_case == True,  # noqa: E712
            TrainingCase.archive_status == CaseArchiveStatusEnum.ACTIVE.value,
        )
        .order_by(TrainingCase.id.asc())
        .all()
    )


def _sessions(db: Session, paper_id: int, user_id: Optional[int] = None) -> List[PracticeSession]:
    query = db.query(PracticeSession).filter(PracticeSession.exam_paper_id == paper_id)
    if user_id is not None:
        query = query.filter(PracticeSession.user_id == user_id)
    return query.order_by(PracticeSession.exam_index.asc(), PracticeSession.id.asc()).all()


def _started_at(rows: List[PracticeSession]) -> Optional[datetime]:
    times = [row.started_at for row in rows if row.started_at]
    return min(times) if times else None


def seconds_left(paper: ExamPaper, rows: List[PracticeSession], now: Optional[datetime] = None) -> int:
    if paper.status == "CLOSED":
        return 0
    start = _started_at(rows)
    if start is None:
        return -1
    deadline = start + timedelta(minutes=int(paper.duration_minutes or 0))
    return max(0, int((deadline - (now or datetime.now())).total_seconds()))


def clock_expired(db: Session, record: PracticeSession, now: Optional[datetime] = None) -> bool:
    paper_id = int(record.exam_paper_id or 0)
    if not paper_id:
        return False
    paper = db.query(ExamPaper).filter(ExamPaper.id == paper_id).first()
    if paper is None or paper.status == "CLOSED":
        return False
    rows = _sessions(db, paper.id, record.user_id)
    left = seconds_left(paper, rows, now)
    return left == 0 and _started_at(rows) is not None


def paper_face(db: Session, record: PracticeSession) -> dict:
    """给练习详情附上这场考试的限时、能否回上一题、题目导航。"""
    blank = {
        "exam_paper_id": 0,
        "exam_title": "",
        "allow_back": False,
        "exam_seconds_left": -1,
        "paper_closed": False,
        "exam_pass_score": 0,
        "prev_session_id": 0,
        "prev_case_id": 0,
        "exam_items": [],
    }
    paper_id = int(getattr(record, "exam_paper_id", 0) or 0)
    if not paper_id:
        return blank
    paper = db.query(ExamPaper).filter(ExamPaper.id == paper_id).first()
    if paper is None:
        return blank
    rows = _sessions(db, paper.id, record.user_id)
    prev = next((row for row in rows if row.exam_index == (record.exam_index or 0) - 1), None)
    allow = bool(paper.allow_back)
    return {
        "exam_paper_id": paper.id,
        "exam_title": paper.title or "",
        "allow_back": allow,
        "exam_seconds_left": seconds_left(paper, rows),
        "paper_closed": paper.status == "CLOSED",
        "exam_pass_score": int(paper.pass_score or 0),
        "prev_session_id": int(prev.id) if allow and prev else 0,
        "prev_case_id": int(prev.case_id) if allow and prev else 0,
        "exam_items": [
            ExamNavItem(
                index=row.exam_index or 0,
                session_id=row.id,
                case_id=row.case_id,
                status=row.status or "",
            )
            for row in rows
        ],
    }


def answers_locked_by_paper(db: Session, record: PracticeSession) -> bool:
    paper_id = int(getattr(record, "exam_paper_id", 0) or 0)
    if not paper_id:
        return False
    paper = db.query(ExamPaper).filter(ExamPaper.id == paper_id).first()
    return paper is None or paper.status != "CLOSED"


def guard_back(db: Session, record: PracticeSession) -> None:
    paper_id = int(record.exam_paper_id or 0)
    if not paper_id:
        return
    paper = db.query(ExamPaper).filter(ExamPaper.id == paper_id).first()
    if paper is None or paper.allow_back or paper.status == "CLOSED":
        return
    drafts = [
        row for row in _sessions(db, paper.id, record.user_id)
        if row.status == PracticeStatusEnum.DRAFT.value
    ]
    if drafts and record.id != drafts[0].id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="这场考试不能返回上一题",
        )


def apply_draft(db: Session, record: PracticeSession, params: PracticeSubmitParams) -> None:
    record.student_dr_grade = params.student_dr_grade or ""
    record.student_diagnosis = params.student_diagnosis or ""
    record.student_diagnosis_form = params.diagnosis or None
    record.student_annotations = [item.model_dump(by_alias=False) for item in params.annotations]
    record.student_measurements = [item.model_dump(by_alias=False) for item in params.measurements]
    record.viewport_snapshot = params.viewport
    record.text_answers = [
        {"id": row.id, "value": row.value or ""}
        for row in params.text_answers
    ]
    if params.duration_seconds:
        record.duration_seconds = params.duration_seconds
    db.flush()


def finalize_user(db: Session, user_id: int, paper_id: int) -> int:
    """把这名学员还没交的题按已保存的内容评分。返回补交题数。"""
    rows = [
        row for row in _sessions(db, paper_id, user_id)
        if row.status == PracticeStatusEnum.DRAFT.value
    ]
    owner = db.query(User).filter(User.id == user_id).first()
    if owner is None:
        return 0
    count = 0
    for row in rows:
        saved = PracticeSubmitParams(
            session_id=row.id,
            student_dr_grade=row.student_dr_grade or "",
            student_diagnosis=row.student_diagnosis or "",
            diagnosis=row.student_diagnosis_form or {},
            annotations=[
                PracticeAnnotation.model_validate(item)
                for item in (row.student_annotations or [])
                if isinstance(item, dict)
            ],
            measurements=[
                PracticeAnnotation.model_validate(item)
                for item in (row.student_measurements or [])
                if isinstance(item, dict)
            ],
            text_answers=row.text_answers or [],
            viewport=row.viewport_snapshot,
            duration_seconds=row.duration_seconds or 0,
            request_id=f"close-{paper_id}-{row.id}",
        )
        PracticeService.submit(db, owner, saved, _clock=False)
        count += 1
    return count


def expire_if_needed(db: Session, record: PracticeSession) -> None:
    if record.status != PracticeStatusEnum.DRAFT.value:
        return
    if not clock_expired(db, record):
        return
    finalize_user(db, record.user_id, int(record.exam_paper_id or 0))


class ExamService:
    @staticmethod
    def case_options(db: Session, user: User) -> list:
        _require_teacher(user)
        from app.schemas.exam import ExamCaseOption
        return [
            ExamCaseOption(
                id=case.id,
                case_no=case.case_no,
                title=case.title or "",
                category=case.category or "",
                category_text=CATEGORY_TEXT.get(case.category, case.category or ""),
                difficulty=case.difficulty or "",
                difficulty_text=DIFFICULTY_TEXT.get(case.difficulty, case.difficulty or ""),
            )
            for case in _pool(db)
        ]

    @staticmethod
    def create(db: Session, user: User, params: ExamCreate) -> ExamPaperOut:
        _require_teacher(user)
        title = (params.title or "").strip()
        if not title:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请填写考试名称")
        mode = (params.pick_mode or "SELECTED").upper()
        if mode not in ("SELECTED", "DRAW"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="抽题方式不正确")
        pool = {case.id: case for case in _pool(db)}
        if mode == "SELECTED":
            ids = []
            for raw in params.case_ids:
                case_id = int(raw)
                if case_id in ids:
                    continue
                if case_id not in pool:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="有病例还没加入实训，不能放进考试",
                    )
                ids.append(case_id)
            if not ids:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请至少选择一份病例")
            if len(ids) > 20:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="一场考试最多 20 题")
        else:
            matched = list(pool.values())
            category = (params.category or "").strip()
            difficulty = (params.difficulty or "").strip()
            if category:
                matched = [case for case in matched if case.category == category]
            if difficulty:
                matched = [case for case in matched if case.difficulty == difficulty]
            want = int(params.question_count or 0)
            if len(matched) < want:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"符合条件的病例只有 {len(matched)} 份，不够抽出 {want} 题",
                )
            if category or difficulty:
                from random import shuffle
                shuffle(matched)
                picked = matched[:want]
            else:
                picked = _pick_across_grades(matched, want)
            ids = [case.id for case in picked]
        paper = ExamPaper(
            title=title,
            teacher_id=user.id,
            status="OPEN",
            duration_minutes=int(params.duration_minutes),
            pass_score=int(params.pass_score),
            allow_back=bool(params.allow_back),
            pick_mode=mode,
            category=(params.category or "").strip(),
            difficulty=(params.difficulty or "").strip(),
            case_ids=ids,
            opened_at=datetime.now(),
        )
        db.add(paper)
        db.commit()
        db.refresh(paper)
        return ExamService._out(db, paper, user)

    @staticmethod
    def list_papers(db: Session, user: User) -> List[ExamPaperOut]:
        rows = db.query(ExamPaper).order_by(ExamPaper.id.desc()).all()
        if _is_teacher_or_admin(user):
            return [ExamService._out(db, row, user) for row in rows]
        visible = []
        for row in rows:
            mine = _sessions(db, row.id, user.id)
            if row.status == "OPEN" or mine:
                visible.append(ExamService._out(db, row, user))
        return visible

    @staticmethod
    def _out(db: Session, paper: ExamPaper, user: User) -> ExamPaperOut:
        ids = [int(item) for item in (paper.case_ids or [])]
        cases = db.query(TrainingCase).filter(TrainingCase.id.in_(ids)).all() if ids else []
        by_id = {case.id: case.case_no for case in cases}
        people = _sessions(db, paper.id)
        by_user: dict = {}
        for row in people:
            by_user.setdefault(row.user_id, []).append(row)
        handed = sum(
            1 for rows in by_user.values()
            if rows and all(row.status != PracticeStatusEnum.DRAFT.value for row in rows)
        )
        mine_rows = by_user.get(user.id, [])
        if not mine_rows:
            mine = "ABSENT" if paper.status == "CLOSED" else "READY"
        elif any(row.status == PracticeStatusEnum.DRAFT.value for row in mine_rows):
            mine = "DOING"
        else:
            mine = "HANDED"
        return ExamPaperOut(
            id=paper.id,
            title=paper.title,
            status=paper.status,
            duration_minutes=paper.duration_minutes,
            pass_score=paper.pass_score,
            allow_back=bool(paper.allow_back),
            pick_mode=paper.pick_mode,
            category=paper.category or "",
            difficulty=paper.difficulty or "",
            case_ids=ids,
            question_count=len(ids),
            case_nos=[by_id.get(case_id, "") for case_id in ids],
            entered_count=len(by_user),
            handed_count=handed,
            opened_at=paper.opened_at,
            closed_at=paper.closed_at,
            mine_status=mine,
        )

    @staticmethod
    def start(db: Session, user: User, paper_id: int):
        if _is_teacher_or_admin(user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="请用学员账号进入考试")
        paper = _paper_or_404(db, paper_id)
        existing = _sessions(db, paper.id, user.id)
        if existing:
            draft = next((row for row in existing if row.status == PracticeStatusEnum.DRAFT.value), None)
            target = draft or existing[0]
            expire_if_needed(db, target)
            db.refresh(target)
            if not paper.allow_back and target.status == PracticeStatusEnum.DRAFT.value:
                guard_back(db, target)
            return _to_out(target, db)
        if paper.status != "OPEN":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="这场考试已经收卷")
        ids = [int(item) for item in (paper.case_ids or [])]
        cases = db.query(TrainingCase).filter(TrainingCase.id.in_(ids)).all() if ids else []
        by_id = {case.id: case for case in cases}
        ordered = [by_id[case_id] for case_id in ids if case_id in by_id]
        if not ordered:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="这场考试没有可用题目")
        group_id = f"paper-{paper.id}-{user.id}"
        first = None
        now = datetime.now()
        for index, case in enumerate(ordered, start=1):
            record = PracticeSession(
                user_id=user.id,
                case_id=case.id,
                mode="SELECTED",
                attempt_kind="EXAM",
                exam_group_id=group_id,
                exam_index=index,
                exam_total=len(ordered),
                exam_paper_id=paper.id,
                status=PracticeStatusEnum.DRAFT.value,
                started_at=now,
            )
            db.add(record)
            db.flush()
            from app.services.practice_service import _ensure_text_paper
            _ensure_text_paper(record)
            if first is None:
                first = record
        db.commit()
        db.refresh(first)
        return _to_out(first, db)

    @staticmethod
    def save_draft(db: Session, user: User, paper_id: int, params: PracticeSubmitParams):
        paper = _paper_or_404(db, paper_id)
        record = _own_draft(db, user, paper, params.session_id)
        if not paper.allow_back:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="这场考试要按顺序作答，不能先保存后返回")
        if clock_expired(db, record):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="考试时间已到，请交卷")
        apply_draft(db, record, params)
        db.commit()
        db.refresh(record)
        return _to_out(record, db)

    @staticmethod
    def hand_in(db: Session, user: User, paper_id: int, body):
        paper = _paper_or_404(db, paper_id)
        if paper.status == "CLOSED":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="这场考试已经收卷")
        params = hand_in_as_submit(body)
        record = (
            db.query(PracticeSession)
            .filter(
                PracticeSession.id == params.session_id,
                PracticeSession.exam_paper_id == paper.id,
                PracticeSession.user_id == user.id,
            )
            .first()
        )
        if record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="没有这份答卷")
        if record.status == PracticeStatusEnum.DRAFT.value:
            apply_draft(db, record, params)
            db.commit()
        finalize_user(db, user.id, paper.id)
        db.refresh(record)
        return _to_out(record, db)

    @staticmethod
    def collect(db: Session, user: User, paper_id: int) -> dict:
        _require_teacher(user)
        paper = _paper_or_404(db, paper_id)
        if paper.status == "CLOSED":
            return {"collected": 0, "message": "已经收过卷"}
        user_ids = {row.user_id for row in _sessions(db, paper.id)}
        collected = 0
        for user_id in user_ids:
            collected += finalize_user(db, user_id, paper.id)
        paper.status = "CLOSED"
        paper.closed_at = datetime.now()
        db.commit()
        return {"collected": collected, "entered": len(user_ids), "message": "已收卷"}

    @staticmethod
    def remove(db: Session, user: User, paper_id: int) -> None:
        _require_teacher(user)
        paper = _paper_or_404(db, paper_id)
        if _sessions(db, paper.id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="已有学员进入，不能删除")
        if paper.status == "CLOSED":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="已收卷的考试要留档")
        db.delete(paper)
        db.commit()

    @staticmethod
    def grade_rows(db: Session, paper: ExamPaper) -> List[dict]:
        sessions = _sessions(db, paper.id)
        by_user: dict = {}
        for row in sessions:
            by_user.setdefault(row.user_id, []).append(row)
        students = (
            db.query(User)
            .join(Role)
            .filter(Role.code == RoleEnum.STUDENT.value, User.is_active == True)  # noqa: E712
            .order_by(User.id.asc())
            .all()
        )
        seen = {student.id for student in students}
        for user_id, rows in by_user.items():
            if user_id not in seen and rows and rows[0].user is not None:
                students.append(rows[0].user)
        question_count = len(paper.case_ids or [])
        out = []
        line = int(paper.pass_score or 0)
        for student in students:
            mine = by_user.get(student.id, [])
            by_index = {row.exam_index: row for row in mine}
            scores = []
            for index in range(1, question_count + 1):
                row = by_index.get(index)
                if row is None or row.status == PracticeStatusEnum.DRAFT.value:
                    scores.append(None)
                else:
                    scores.append(round(float(row.score_total or 0), 2))
            if not mine:
                state, average, passed = "缺考", None, "缺考"
            elif any(row.status == PracticeStatusEnum.DRAFT.value for row in mine):
                state, average, passed = "未交完", None, "未交完"
            else:
                state = "已交卷"
                nums = [score for score in scores if score is not None]
                average = round(sum(nums) / len(nums), 2) if nums else 0.0
                passed = "合格" if average >= line else "不合格"
            out.append({
                "name": student.real_name or student.username,
                "username": student.username,
                "state": state,
                "scores": scores,
                "average": average,
                "pass_score": line,
                "passed": passed,
            })
        return out

    @staticmethod
    def csv_text(db: Session, user: User, paper_id: int) -> str:
        _require_teacher(user)
        paper = _paper_or_404(db, paper_id)
        if paper.status != "CLOSED":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先收卷，再导出成绩")
        ids = [int(item) for item in (paper.case_ids or [])]
        cases = db.query(TrainingCase).filter(TrainingCase.id.in_(ids)).all() if ids else []
        case_no = {case.id: case.case_no for case in cases}
        headers = ["姓名", "用户名", "状态"]
        for index, case_id in enumerate(ids, start=1):
            headers.append(f"第{index}题({case_no.get(case_id, case_id)})")
        headers.extend(["平均分", "合格线", "是否合格"])
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(headers)
        for row in ExamService.grade_rows(db, paper):
            scores = ["" if score is None else score for score in row["scores"]]
            average = "" if row["average"] is None else row["average"]
            writer.writerow([
                row["name"], row["username"], row["state"], *scores,
                average, row["pass_score"], row["passed"],
            ])
        return buffer.getvalue()


def _own_draft(db: Session, user: User, paper: ExamPaper, session_id: int) -> PracticeSession:
    record = (
        db.query(PracticeSession)
        .filter(
            PracticeSession.id == session_id,
            PracticeSession.exam_paper_id == paper.id,
            PracticeSession.user_id == user.id,
        )
        .first()
    )
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="没有这份答卷")
    if record.status != PracticeStatusEnum.DRAFT.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="这题已经交过")
    if paper.status != "OPEN":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="这场考试已经收卷")
    guard_back(db, record)
    return record
