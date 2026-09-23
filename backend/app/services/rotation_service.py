# -*- coding: utf-8 -*-
"""本轮转必做。学员首页只给病例编号，不把带分级的标题发下去。"""

from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import (
    CaseArchiveStatusEnum,
    LearningResource,
    PracticeSession,
    PracticeStatusEnum,
    ResourceStatusEnum,
    ResourceTypeEnum,
    Role,
    RoleEnum,
    Rotation,
    RotationStatusEnum,
    RotationTask,
    RotationTaskAck,
    RotationTaskKindEnum,
    TrainingCase,
    User,
)
from app.schemas.rotation import (
    GroupSummary,
    OptionItem,
    RotationBrief,
    RotationOptionsOut,
    RotationUpdate,
    StudentGroupUpdate,
    StudentHomeOut,
    StudentProgressOut,
    StudentTaskSnap,
    TaskCreate,
    TaskOrder,
    TaskOut,
    TeacherHomeOut,
    WeakLabelBrief,
)
from app.services.common_service import learner_progress

_DONE = {"DONE", "LEARNED"}
_OPEN = {"TODO", "DOING", "SHORT"}
_UNGROUPED = "未分组"


def _group_label(value: str) -> str:
    text = (value or "").strip()
    return text or _UNGROUPED


def _tier(task: RotationTask) -> str:
    return getattr(task, "tier", None) or "REQUIRED"


def _scope_text(task: RotationTask) -> str:
    scope = getattr(task, "scope", None) or "ALL"
    value = (getattr(task, "scope_value", None) or "").strip()
    if scope == "YEAR":
        return value
    if scope == "GROUP":
        return value
    return "全部"


def _visible_to(task: RotationTask, student: User) -> bool:
    scope = getattr(task, "scope", None) or "ALL"
    value = (getattr(task, "scope_value", None) or "").strip()
    if scope == "YEAR":
        return bool(value) and (student.study_year or "").strip() == value
    if scope == "GROUP":
        return bool(value) and (student.mentor_group or "").strip() == value
    return True


def _case_heading(task: RotationTask, case_no: str) -> str:
    prefix = "拓展病例" if _tier(task) == "EXTENSION" else "必做病例"
    return f"{prefix} {case_no}".strip()


def _normalize_scope(params: TaskCreate) -> Tuple[str, str]:
    scope = params.scope or "ALL"
    value = (params.scope_value or "").strip()[:32]
    if scope == "ALL":
        return "ALL", ""
    if scope not in ("YEAR", "GROUP"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请选择全部、年级或轮转组")
    if not value or value == _UNGROUPED:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请选择具体的年级或轮转组")
    return scope, value


def _is_teacher(user: User) -> bool:
    code = user.role.code if user.role else ""
    return code in (RoleEnum.TEACHER.value, RoleEnum.ADMIN.value)


def _today() -> str:
    return date.today().isoformat()


def _active(db: Session) -> Optional[Rotation]:
    return (
        db.query(Rotation)
        .filter(Rotation.status == RotationStatusEnum.ACTIVE.value)
        .order_by(Rotation.id.desc())
        .first()
    )


def _students(db: Session) -> List[User]:
    return (
        db.query(User)
        .join(Role, User.role_id == Role.id)
        .filter(Role.code == RoleEnum.STUDENT.value)
        .order_by(User.id.asc())
        .all()
    )


def _tasks(db: Session, rotation_id: int) -> List[RotationTask]:
    rows = (
        db.query(RotationTask)
        .filter(RotationTask.rotation_id == rotation_id)
        .order_by(RotationTask.sort_order.asc(), RotationTask.id.asc())
        .all()
    )
    case_ids = [task.case_id for task in rows if task.kind == RotationTaskKindEnum.CASE.value and task.case_id]
    open_ids = set()
    if case_ids:
        open_ids = {
            row[0]
            for row in db.query(TrainingCase.id)
            .filter(
                TrainingCase.id.in_(case_ids),
                TrainingCase.is_published == True,  # noqa: E712
                TrainingCase.is_train_case == True,  # noqa: E712
                TrainingCase.archive_status == CaseArchiveStatusEnum.ACTIVE.value,
            )
            .all()
        }
    return [
        task
        for task in rows
        if task.kind != RotationTaskKindEnum.CASE.value or task.case_id in open_ids
    ]


def ensure_rotation(db: Session, user: User) -> Rotation:
    """没有进行中的轮转时，用已加入实训的眼底病例建一份，方便首页不是空的。"""
    found = _active(db)
    if found is not None:
        return found
    teacher = (
        db.query(User)
        .join(Role, User.role_id == Role.id)
        .filter(Role.code.in_([RoleEnum.TEACHER.value, RoleEnum.ADMIN.value]))
        .order_by(User.id.asc())
        .first()
    )
    creator_id = teacher.id if teacher is not None else user.id
    today = date.today()
    rotation = Rotation(
        title="本轮转 · 眼底病谱",
        start_on=today.isoformat(),
        due_on=(today + timedelta(days=28)).isoformat(),
        pass_score=60,
        status=RotationStatusEnum.ACTIVE.value,
        creator_id=creator_id,
    )
    db.add(rotation)
    db.flush()
    cases = (
        db.query(TrainingCase)
        .filter(
            TrainingCase.is_published == True,  # noqa: E712
            TrainingCase.is_train_case == True,  # noqa: E712
            TrainingCase.archive_status == CaseArchiveStatusEnum.ACTIVE.value,
            TrainingCase.category.in_(("DR", "NORMAL")),
        )
        .order_by(TrainingCase.gold_dr_grade.asc(), TrainingCase.case_no.asc())
        .all()
    )
    order = 0
    for case in cases:
        order += 1
        db.add(RotationTask(
            rotation_id=rotation.id,
            kind=RotationTaskKindEnum.CASE.value,
            case_id=case.id,
            title=f"必做病例 {case.case_no}",
            summary="完成本例练习，达到合格分。",
            pass_score=int(case.pass_score or rotation.pass_score),
            due_on="",
            sort_order=order,
        ))
    resources = (
        db.query(LearningResource)
        .filter(
            LearningResource.status == ResourceStatusEnum.PUBLISHED.value,
            LearningResource.resource_type == ResourceTypeEnum.KNOWLEDGE.value,
        )
        .order_by(LearningResource.id.asc())
        .limit(2)
        .all()
    )
    if resources:
        for res in resources:
            order += 1
            db.add(RotationTask(
                rotation_id=rotation.id,
                kind=RotationTaskKindEnum.KNOWLEDGE.value,
                resource_id=res.id,
                title=res.title,
                summary=res.summary or "阅读后在首页标记已学。",
                pass_score=0,
                due_on="",
                sort_order=order,
            ))
    else:
        order += 1
        db.add(RotationTask(
            rotation_id=rotation.id,
            kind=RotationTaskKindEnum.KNOWLEDGE.value,
            title="必学知识点：糖网从正常眼底到 PDR",
            summary="分清正常眼底、轻度到重度 NPDR。增殖性糖尿病视网膜病变（PDR）必须见到新生血管，视网膜前积血不能代替新生血管。读完后在本页标记已学。",
            pass_score=0,
            due_on="",
            sort_order=order,
        ))
    db.commit()
    db.refresh(rotation)
    return rotation


def _due(task: RotationTask, rotation: Rotation) -> str:
    return (task.due_on or "").strip() or (rotation.due_on or "")


def _flag_due(due_on: str, done: bool) -> Tuple[bool, bool]:
    if done or not due_on:
        return False, False
    today = _today()
    return due_on < today, due_on == today


def _case_state(
    db: Session, user_id: int, case_id: int, pass_score: int,
) -> Tuple[str, str, Optional[float]]:
    from app.services.practice_service import exam_locks_answers

    rows = (
        db.query(PracticeSession)
        .filter(
            PracticeSession.user_id == user_id,
            PracticeSession.case_id == case_id,
        )
        .all()
    )
    if not rows:
        return "TODO", "未开始", None
    locked = exam_locks_answers(db, user_id, case_id)
    submitted = [
        row for row in rows
        if row.status in (
            PracticeStatusEnum.SUBMITTED.value,
            PracticeStatusEnum.REVIEWED.value,
        )
        and not (_is_exam_locked(row, locked))
    ]
    if any(bool(row.is_passed) or float(row.score_total or 0) >= pass_score for row in submitted):
        best = max(float(row.score_total or 0) for row in submitted)
        return "DONE", "已合格", round(best, 1)
    if submitted:
        best = max(float(row.score_total or 0) for row in submitted)
        return "SHORT", "未合格", round(best, 1)
    return "DOING", "进行中", None


def _is_exam_locked(row: PracticeSession, locked: bool) -> bool:
    return locked and (row.attempt_kind or "") == "EXAM"


def _ack_ids(db: Session, user_id: int, task_ids: List[int]) -> set:
    if not task_ids:
        return set()
    rows = (
        db.query(RotationTaskAck.task_id)
        .filter(
            RotationTaskAck.user_id == user_id,
            RotationTaskAck.task_id.in_(task_ids),
        )
        .all()
    )
    return {row[0] for row in rows}


def _student_task(
    db: Session,
    task: RotationTask,
    rotation: Rotation,
    user_id: int,
    acked: set,
    case_no: str,
) -> TaskOut:
    if task.kind == RotationTaskKindEnum.CASE.value and task.case_id:
        status_code, status_text, score = _case_state(
            db, user_id, task.case_id, int(task.pass_score or rotation.pass_score),
        )
        title = _case_heading(task, case_no)
    elif task.id in acked:
        status_code, status_text, score = "LEARNED", "已学习", None
        title = task.title
    else:
        status_code, status_text, score = "TODO", "未学习", None
        title = task.title
    due = _due(task, rotation)
    overdue, due_today = _flag_due(due, status_code in _DONE)
    if task.kind == RotationTaskKindEnum.CASE.value:
        kind_text = "拓展病例" if _tier(task) == "EXTENSION" else "必做病例"
    else:
        kind_text = "必学知识点"
    return TaskOut(
        id=task.id,
        kind=task.kind,
        kind_text=kind_text,
        title=title,
        summary=task.summary or "",
        due_on=due,
        pass_score=int(task.pass_score or 0),
        status=status_code,
        status_text=status_text,
        score=score,
        overdue=overdue,
        due_today=due_today,
        case_id=task.case_id,
        case_no=case_no,
        resource_id=task.resource_id,
        tier=_tier(task),
        scope=getattr(task, "scope", None) or "ALL",
        scope_value=(getattr(task, "scope_value", None) or ""),
        scope_text=_scope_text(task),
    )


def _brief(rotation: Rotation, tasks: List[TaskOut]) -> RotationBrief:
    total = len(tasks)
    done = sum(1 for task in tasks if task.status in _DONE)
    progress = int(round(100 * done / total)) if total else 0
    return RotationBrief(
        id=rotation.id,
        title=rotation.title,
        start_on=rotation.start_on or "",
        due_on=rotation.due_on or "",
        pass_score=int(rotation.pass_score or 60),
        total=total,
        done=done,
        progress=progress,
    )


def _case_numbers(db: Session, tasks: List[RotationTask]) -> Dict[int, str]:
    ids = [task.case_id for task in tasks if task.case_id]
    if not ids:
        return {}
    rows = db.query(TrainingCase.id, TrainingCase.case_no).filter(TrainingCase.id.in_(ids)).all()
    return {row[0]: row[1] for row in rows}


class RotationService:

    @staticmethod
    def home(db: Session, user: User):
        rotation = ensure_rotation(db, user)
        tasks = _tasks(db, rotation.id)
        if _is_teacher(user):
            return RotationService._teacher(db, rotation, tasks)
        return RotationService._student(db, user, rotation, tasks)

    @staticmethod
    def _student(db: Session, user: User, rotation: Rotation, tasks: List[RotationTask]) -> StudentHomeOut:
        visible = [task for task in tasks if _visible_to(task, user)]
        numbers = _case_numbers(db, visible)
        acked = _ack_ids(db, user.id, [task.id for task in visible])
        rows = [
            _student_task(db, task, rotation, user.id, acked, numbers.get(task.case_id or 0, ""))
            for task in visible
        ]
        required = [row for row in rows if row.tier != "EXTENSION"]
        today = [row for row in required if row.status in _OPEN]
        today.sort(key=lambda row: (not row.overdue, not row.due_today, row.due_on, row.id))
        return StudentHomeOut(
            rotation=_brief(rotation, required),
            today=today,
            tasks=rows,
            study_year=_group_label(getattr(user, "study_year", "")),
            rotation_batch=_group_label(getattr(user, "rotation_batch", "")),
            mentor_group=_group_label(getattr(user, "mentor_group", "")),
        )

    @staticmethod
    def _teacher(db: Session, rotation: Rotation, tasks: List[RotationTask]) -> TeacherHomeOut:
        students = _students(db)
        numbers = _case_numbers(db, tasks)
        case_titles = {}
        case_ids = [task.case_id for task in tasks if task.case_id]
        if case_ids:
            for row in db.query(TrainingCase).filter(TrainingCase.id.in_(case_ids)).all():
                case_titles[row.id] = row.title or row.case_no
        acked_by = {
            student.id: _ack_ids(db, student.id, [task.id for task in tasks])
            for student in students
        }
        teacher_rows: List[TaskOut] = []
        for task in tasks:
            audience = [student for student in students if _visible_to(task, student)]
            states = [
                _student_task(
                    db, task, rotation, student.id, acked_by[student.id],
                    numbers.get(task.case_id or 0, ""),
                )
                for student in audience
            ]
            done_count = sum(1 for row in states if row.status in _DONE and row.tier != "EXTENSION")
            if _tier(task) == "EXTENSION":
                done_count = sum(1 for row in states if row.status in _DONE)
            title = case_titles.get(task.case_id or 0) or task.title
            due = _due(task, rotation)
            finished = bool(audience) and done_count == len(audience)
            overdue, due_today = _flag_due(due, finished)
            if task.kind == RotationTaskKindEnum.CASE.value:
                kind_text = "拓展病例" if _tier(task) == "EXTENSION" else "必做病例"
            else:
                kind_text = "必学知识点"
            status_text = (
                f"{done_count}/{len(audience)} 人完成"
                if audience
                else "没有对上的学员"
            )
            teacher_rows.append(TaskOut(
                id=task.id,
                kind=task.kind,
                kind_text=kind_text,
                title=title,
                summary=task.summary or "",
                due_on=due,
                pass_score=int(task.pass_score or 0),
                status="DONE" if finished else "TODO",
                status_text=status_text,
                overdue=overdue,
                due_today=due_today,
                case_id=task.case_id,
                case_no=numbers.get(task.case_id or 0, ""),
                resource_id=task.resource_id,
                done_count=done_count,
                student_count=len(audience),
                tier=_tier(task),
                scope=getattr(task, "scope", None) or "ALL",
                scope_value=getattr(task, "scope_value", None) or "",
                scope_text=_scope_text(task),
            ))
        progress_rows = []
        practice_map = learner_progress(db, [student.id for student in students])
        for student in students:
            visible = [task for task in tasks if _visible_to(task, student)]
            bundle = [
                _student_task(
                    db, task, rotation, student.id, acked_by[student.id],
                    numbers.get(task.case_id or 0, ""),
                )
                for task in visible
            ]
            required = [row for row in bundle if row.tier != "EXTENSION"]
            done = sum(1 for row in required if row.status in _DONE)
            total = len(required)
            learned = practice_map[student.id]
            progress_rows.append(StudentProgressOut(
                user_id=student.id,
                name=student.real_name or student.username,
                username=student.username or "",
                study_year=_group_label(getattr(student, "study_year", "")),
                rotation_batch=_group_label(getattr(student, "rotation_batch", "")),
                mentor_group=_group_label(getattr(student, "mentor_group", "")),
                done=done,
                total=total,
                progress=int(round(100 * done / total)) if total else 0,
                practice_count=learned["practice_count"],
                completed_cases=learned["completed_cases"],
                avg_score=learned["avg_score"],
                study_seconds=learned["total_seconds"],
                tasks=[
                    StudentTaskSnap(
                        task_id=row.id,
                        status=row.status,
                        status_text=row.status_text,
                        score=row.score,
                    )
                    for row in bundle
                ],
            ))
        required_rows = [row for row in teacher_rows if row.tier != "EXTENSION"]
        return TeacherHomeOut(
            rotation=RotationBrief(
                id=rotation.id,
                title=rotation.title,
                start_on=rotation.start_on or "",
                due_on=rotation.due_on or "",
                pass_score=int(rotation.pass_score or 60),
                total=len(required_rows),
                done=sum(
                    1 for row in required_rows
                    if row.student_count and row.done_count == row.student_count
                ),
                progress=_class_progress(required_rows),
            ),
            tasks=teacher_rows,
            students=progress_rows,
            groups=_group_summaries(db, progress_rows),
        )

    @staticmethod
    def options(db: Session, user: User) -> RotationOptionsOut:
        if not _is_teacher(user):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "只有教师可以布置轮转任务")
        cases = (
            db.query(TrainingCase)
            .filter(
                TrainingCase.is_published == True,  # noqa: E712
                TrainingCase.is_train_case == True,  # noqa: E712
                TrainingCase.archive_status == CaseArchiveStatusEnum.ACTIVE.value,
            )
            .order_by(TrainingCase.case_no.asc())
            .all()
        )
        resources = (
            db.query(LearningResource)
            .filter(LearningResource.status == ResourceStatusEnum.PUBLISHED.value)
            .order_by(LearningResource.id.asc())
            .all()
        )
        return RotationOptionsOut(
            cases=[OptionItem(id=row.id, label=f"{row.case_no} · {row.title}") for row in cases],
            resources=[OptionItem(id=row.id, label=row.title) for row in resources],
        )

    @staticmethod
    def update_rotation(db: Session, user: User, params: RotationUpdate) -> TeacherHomeOut:
        if not _is_teacher(user):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "只有教师可以修改轮转")
        rotation = ensure_rotation(db, user)
        if params.title is not None and params.title.strip():
            rotation.title = params.title.strip()[:80]
        if params.due_on is not None:
            _parse_day(params.due_on)
            rotation.due_on = params.due_on.strip()
        if params.pass_score is not None:
            rotation.pass_score = int(params.pass_score)
        db.commit()
        return RotationService._teacher(db, rotation, _tasks(db, rotation.id))

    @staticmethod
    def set_student_group(db: Session, user: User, student_id: int, params: StudentGroupUpdate) -> TeacherHomeOut:
        if not _is_teacher(user):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "只有教师可以调整学员分组")
        student = db.query(User).filter(User.id == student_id).first()
        if student is None or not student.role or student.role.code != RoleEnum.STUDENT.value:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "学员不存在")
        student.study_year = (params.study_year or "").strip()[:32]
        student.rotation_batch = (params.rotation_batch or "").strip()[:32]
        student.mentor_group = (params.mentor_group or "").strip()[:32]
        db.commit()
        rotation = ensure_rotation(db, user)
        return RotationService._teacher(db, rotation, _tasks(db, rotation.id))

    @staticmethod
    def add_task(db: Session, user: User, params: TaskCreate) -> TeacherHomeOut:
        if not _is_teacher(user):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "只有教师可以布置任务")
        rotation = ensure_rotation(db, user)
        if params.due_on.strip():
            _parse_day(params.due_on)
        if params.kind == "CASE":
            if not params.case_id:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "请选择病例")
            case = db.query(TrainingCase).filter(TrainingCase.id == params.case_id).first()
            if case is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "病例不存在")
            if (
                not case.is_published
                or not case.is_train_case
                or case.archive_status != CaseArchiveStatusEnum.ACTIVE.value
            ):
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "该病例还没加入实训，学员打不开")
            scope, scope_value = _normalize_scope(params)
            tier = params.tier if params.tier in ("REQUIRED", "EXTENSION") else "REQUIRED"
            exists = (
                db.query(RotationTask)
                .filter(
                    RotationTask.rotation_id == rotation.id,
                    RotationTask.case_id == case.id,
                    RotationTask.scope == scope,
                    RotationTask.scope_value == scope_value,
                )
                .first()
            )
            if exists:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "这例已经布置给同一范围")
            heading = "拓展病例" if tier == "EXTENSION" else "必做病例"
            task = RotationTask(
                rotation_id=rotation.id,
                kind=RotationTaskKindEnum.CASE.value,
                case_id=case.id,
                title=f"{heading} {case.case_no}",
                summary="选做，不计入必做进度。" if tier == "EXTENSION" else "完成本例练习，达到合格分。",
                pass_score=int(params.pass_score if params.pass_score is not None else (case.pass_score or rotation.pass_score)),
                due_on=params.due_on.strip(),
                sort_order=_next_order(db, rotation.id),
                tier=tier,
                scope=scope,
                scope_value=scope_value,
            )
        else:
            title = params.title.strip()
            summary = params.summary.strip()
            resource_id = params.resource_id
            if resource_id:
                res = db.query(LearningResource).filter(LearningResource.id == resource_id).first()
                if res is None or res.status != ResourceStatusEnum.PUBLISHED.value:
                    raise HTTPException(status.HTTP_400_BAD_REQUEST, "知识点资料未发布")
                title = title or res.title
                summary = summary or res.summary or "阅读后在首页标记已学。"
            if not title:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "请填写知识点标题")
            task = RotationTask(
                rotation_id=rotation.id,
                kind=RotationTaskKindEnum.KNOWLEDGE.value,
                resource_id=resource_id,
                title=title[:160],
                summary=summary,
                pass_score=0,
                due_on=params.due_on.strip(),
                sort_order=_next_order(db, rotation.id),
            )
        db.add(task)
        db.commit()
        return RotationService._teacher(db, rotation, _tasks(db, rotation.id))

    @staticmethod
    def reorder(db: Session, user: User, params: TaskOrder) -> TeacherHomeOut:
        if not _is_teacher(user):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "只有教师可以调整顺序")
        rotation = ensure_rotation(db, user)
        rows = (
            db.query(RotationTask)
            .filter(RotationTask.rotation_id == rotation.id)
            .all()
        )
        by_id = {row.id: row for row in rows}
        ordered = [by_id[task_id] for task_id in params.task_ids if task_id in by_id]
        seen = {row.id for row in ordered}
        ordered.extend(row for row in rows if row.id not in seen)
        for index, row in enumerate(ordered, start=1):
            row.sort_order = index
        db.commit()
        return RotationService._teacher(db, rotation, _tasks(db, rotation.id))

    @staticmethod
    def arrange(db: Session, user: User) -> TeacherHomeOut:
        """必做在前、拓展在后；病例按金标准分级从轻到重，知识点留在最后。"""
        if not _is_teacher(user):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "只有教师可以调整顺序")
        rotation = ensure_rotation(db, user)
        rows = (
            db.query(RotationTask)
            .filter(RotationTask.rotation_id == rotation.id)
            .order_by(RotationTask.sort_order.asc(), RotationTask.id.asc())
            .all()
        )
        cases = {}
        case_ids = [row.case_id for row in rows if row.case_id]
        if case_ids:
            cases = {
                row.id: row
                for row in db.query(TrainingCase).filter(TrainingCase.id.in_(case_ids)).all()
            }

        def sort_key(task: RotationTask):
            if task.kind != RotationTaskKindEnum.CASE.value:
                return (2, 0, task.sort_order, task.id)
            case = cases.get(task.case_id or 0)
            raw = (case.gold_dr_grade if case else "") or ""
            try:
                grade = int(raw)
            except ValueError:
                grade = 9
            tier_rank = 1 if _tier(task) == "EXTENSION" else 0
            number = case.case_no if case else ""
            return (tier_rank, grade, number, task.id)

        for index, row in enumerate(sorted(rows, key=sort_key), start=1):
            row.sort_order = index
        db.commit()
        return RotationService._teacher(db, rotation, _tasks(db, rotation.id))

    @staticmethod
    def remove_task(db: Session, user: User, task_id: int) -> TeacherHomeOut:
        if not _is_teacher(user):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "只有教师可以撤下任务")
        rotation = ensure_rotation(db, user)
        task = (
            db.query(RotationTask)
            .filter(RotationTask.id == task_id, RotationTask.rotation_id == rotation.id)
            .first()
        )
        if task is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "任务不存在")
        db.delete(task)
        db.commit()
        return RotationService._teacher(db, rotation, _tasks(db, rotation.id))

    @staticmethod
    def learn(db: Session, user: User, task_id: int) -> StudentHomeOut:
        if _is_teacher(user):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "教师不用标记已学")
        rotation = ensure_rotation(db, user)
        task = (
            db.query(RotationTask)
            .filter(RotationTask.id == task_id, RotationTask.rotation_id == rotation.id)
            .first()
        )
        if task is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "任务不存在")
        if task.kind != RotationTaskKindEnum.KNOWLEDGE.value:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "病例要交卷并达到合格分才算完成")
        exists = (
            db.query(RotationTaskAck)
            .filter(RotationTaskAck.task_id == task.id, RotationTaskAck.user_id == user.id)
            .first()
        )
        if exists is None:
            db.add(RotationTaskAck(task_id=task.id, user_id=user.id))
            db.commit()
        return RotationService._student(db, user, rotation, _tasks(db, rotation.id))


def _group_weak_labels(db: Session, user_ids: List[int]) -> List[WeakLabelBrief]:
    if not user_ids:
        return []
    locked = {
        row[0]
        for row in db.query(PracticeSession.exam_group_id)
        .filter(
            PracticeSession.user_id.in_(user_ids),
            PracticeSession.attempt_kind == "EXAM",
            PracticeSession.status == PracticeStatusEnum.DRAFT.value,
            PracticeSession.exam_group_id != "",
        )
        .all()
        if row[0]
    }
    rows = (
        db.query(PracticeSession)
        .filter(
            PracticeSession.user_id.in_(user_ids),
            PracticeSession.status.in_([
                PracticeStatusEnum.SUBMITTED.value,
                PracticeStatusEnum.REVIEWED.value,
            ]),
        )
        .all()
    )
    counts: dict = {}
    for record in rows:
        if (record.attempt_kind or "") == "EXAM" and (record.exam_group_id or "") in locked:
            continue
        points = record.error_points or []
        if not isinstance(points, list):
            continue
        for point in points:
            if not isinstance(point, dict):
                continue
            label = str(point.get("label") or point.get("expectedLabel") or "").strip()
            if not label:
                continue
            item = counts.setdefault(label, {"missed": 0, "false_positive": 0})
            kind = point.get("type") or ""
            if kind == "missed":
                item["missed"] += 1
            elif kind == "false_positive":
                item["false_positive"] += 1
    ranked = sorted(
        counts.items(),
        key=lambda pair: pair[1]["missed"] + pair[1]["false_positive"],
        reverse=True,
    )
    return [
        WeakLabelBrief(label=label, missed=item["missed"], false_positive=item["false_positive"])
        for label, item in ranked[:5]
        if item["missed"] or item["false_positive"]
    ]


def _group_summaries(db: Session, students: List[StudentProgressOut]) -> List[GroupSummary]:
    buckets: dict = {}
    for student in students:
        key = (student.study_year, student.rotation_batch, student.mentor_group)
        bucket = buckets.setdefault(key, {"ids": [], "done": 0, "total": 0})
        bucket["ids"].append(student.user_id)
        bucket["done"] += student.done
        bucket["total"] += student.total
    summaries = []
    for (year, batch, group), bucket in buckets.items():
        total = bucket["total"]
        summaries.append(GroupSummary(
            study_year=year,
            rotation_batch=batch,
            mentor_group=group,
            student_count=len(bucket["ids"]),
            done=bucket["done"],
            total=total,
            progress=int(round(100 * bucket["done"] / total)) if total else 0,
            weak_labels=_group_weak_labels(db, bucket["ids"]),
        ))
    summaries.sort(key=lambda row: (row.study_year, row.rotation_batch, row.mentor_group))
    return summaries


def _class_progress(rows: List[TaskOut]) -> int:
    slots = sum(row.student_count for row in rows)
    done = sum(row.done_count for row in rows)
    if not slots:
        return 0
    return int(round(100 * done / slots))


def _next_order(db: Session, rotation_id: int) -> int:
    last = (
        db.query(RotationTask.sort_order)
        .filter(RotationTask.rotation_id == rotation_id)
        .order_by(RotationTask.sort_order.desc())
        .first()
    )
    return int(last[0]) + 1 if last else 1


def _parse_day(value: str) -> None:
    text = (value or "").strip()
    try:
        date.fromisoformat(text)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "日期格式应为 YYYY-MM-DD") from exc
