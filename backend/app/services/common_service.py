"""
通用模块业务层
- 系统配置
- 字典
- 医院（mock 静态数据，可按需接入医院主数据）
- 科室 CRUD
- 全院培训统计
- 学员学时汇总
"""

from datetime import datetime
from typing import Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    Department,
    PracticeSession,
    PracticeStatusEnum,
    ReadingAnnotation,
    ReadingStatusEnum,
    Role,
    RoleEnum,
    TrainingCase,
    User,
)

# 「已完成」的口径：草稿不算，提交过就算（教师点评与否不影响完成事实）
_PRACTICE_DONE = (
    PracticeStatusEnum.SUBMITTED.value,
    PracticeStatusEnum.REVIEWED.value,
)
_READING_DONE = (
    ReadingStatusEnum.SUBMITTED.value,
    ReadingStatusEnum.REVIEWED.value,
)

_EMPTY_PROGRESS = {
    "practice_count": 0,
    "completed_cases": 0,
    "avg_score": 0.0,
    "score_sum": 0.0,
    "score_count": 0,
    "total_seconds": 0,
    "avg_iou": 0.0,
    "iou_sum": 0.0,
    "iou_count": 0,
    "passed": 0,
}


def learner_progress(db: Session, user_ids: Optional[List[int]] = None) -> Dict[int, dict]:
    """学员、教师、管理员共用的练习次数、完成病例、平均成绩和学时。

    练习次数、成绩、学时只数已交卷的练习。草稿不算。
    完成病例是已交卷练习和已提交阅片的病例并集，同一病例多次只算一例。
    """
    if user_ids is not None and not user_ids:
        return {}

    practice_q = db.query(
        PracticeSession.user_id,
        PracticeSession.case_id,
        PracticeSession.score_total,
        PracticeSession.duration_seconds,
        PracticeSession.iou_avg,
        PracticeSession.is_passed,
    ).filter(PracticeSession.status.in_(_PRACTICE_DONE))
    reading_q = db.query(
        ReadingAnnotation.user_id,
        ReadingAnnotation.case_id,
    ).filter(ReadingAnnotation.status.in_(_READING_DONE))
    if user_ids is not None:
        practice_q = practice_q.filter(PracticeSession.user_id.in_(user_ids))
        reading_q = reading_q.filter(ReadingAnnotation.user_id.in_(user_ids))

    buckets: Dict[int, dict] = {}

    def bucket(uid: int) -> dict:
        return buckets.setdefault(uid, {
            "practice_count": 0,
            "scores": [],
            "seconds": 0,
            "ious": [],
            "passed": 0,
            "cases": set(),
        })

    for uid, case_id, score, secs, iou, passed in practice_q.all():
        row = bucket(int(uid))
        row["practice_count"] += 1
        if score is not None:
            row["scores"].append(float(score))
        row["seconds"] += int(secs or 0)
        if iou is not None and float(iou) >= 0:
            row["ious"].append(float(iou))
        if passed:
            row["passed"] += 1
        if case_id:
            row["cases"].add(int(case_id))

    for uid, case_id in reading_q.distinct().all():
        if case_id:
            bucket(int(uid))["cases"].add(int(case_id))

    out: Dict[int, dict] = {}
    for uid, row in buckets.items():
        count = row["practice_count"]
        ious = row["ious"]
        scores = row["scores"]
        out[uid] = {
            "practice_count": count,
            "completed_cases": len(row["cases"]),
            "avg_score": round(sum(scores) / len(scores), 2) if scores else 0.0,
            "score_sum": sum(scores),
            "score_count": len(scores),
            "total_seconds": row["seconds"],
            "avg_iou": round(sum(ious) / len(ious), 4) if ious else 0.0,
            "iou_sum": sum(ious),
            "iou_count": len(ious),
            "passed": row["passed"],
        }
    if user_ids is not None:
        for uid in user_ids:
            out.setdefault(uid, dict(_EMPTY_PROGRESS))
    return out


def learner_progress_sum(rows: Dict[int, dict]) -> dict:
    """把每人的数加总。完成病例按人累加，两人完成同一例算两例。"""
    count = sum(row["practice_count"] for row in rows.values())
    seconds = sum(row["total_seconds"] for row in rows.values())
    passed = sum(row["passed"] for row in rows.values())
    cases = sum(row["completed_cases"] for row in rows.values())
    score_count = sum(row["score_count"] for row in rows.values())
    score_sum = sum(row["score_sum"] for row in rows.values())
    iou_count = sum(row["iou_count"] for row in rows.values())
    iou_sum = sum(row["iou_sum"] for row in rows.values())
    return {
        "practice_count": count,
        "completed_cases": cases,
        "avg_score": round(score_sum / score_count, 2) if score_count else 0.0,
        "total_seconds": seconds,
        "avg_iou": round(iou_sum / iou_count, 4) if iou_count else 0.0,
        "passed": passed,
    }
from app.schemas.common import (
    DepartmentMemberOut,
    DepartmentOut,
    DepartmentSaveParams,
    DictItemOut,
    HospitalOut,
    StudyHoursItem,
    StudyHoursOut,
    SystemConfigOut,
    TrainingOverviewItem,
    TrainingOverviewOut,
)


# ============================================================
#                    内置静态字典
# ============================================================

_DICTS: Dict[str, List[Dict]] = {
    # DR 分级
    "dr_level": [
        {"code": "0", "label": "0 级 无 DR", "sort": 0},
        {"code": "1", "label": "1 级 轻度 NPDR", "sort": 1},
        {"code": "2", "label": "2 级 中度 NPDR", "sort": 2},
        {"code": "3", "label": "3 级 重度 NPDR", "sort": 3},
        {"code": "4", "label": "4 级 PDR（增殖性）", "sort": 4},
    ],
    # 病变类型
    "lesion_type": [
        {"code": "MA", "label": "微动脉瘤", "sort": 1, "remark": "Microaneurysm"},
        {"code": "HM", "label": "出血", "sort": 2, "remark": "Hemorrhage"},
        {"code": "HE", "label": "渗出", "sort": 3, "remark": "Hard Exudate"},
        {"code": "SE", "label": "棉绒斑", "sort": 4, "remark": "Soft Exudate / CWS"},
        {"code": "NV", "label": "新生血管", "sort": 5, "remark": "Neovascularization"},
    ],
    # 风险等级
    "risk_level": [
        {"code": "green", "label": "低风险", "sort": 1},
        {"code": "yellow", "label": "中风险", "sort": 2},
        {"code": "red", "label": "高风险", "sort": 3},
    ],
    # 眼别
    "eye_side": [
        {"code": "OD", "label": "右眼", "sort": 1},
        {"code": "OS", "label": "左眼", "sort": 2},
        {"code": "OU", "label": "双眼", "sort": 3},
    ],
    # 性别
    "gender": [
        {"code": "男", "label": "男", "sort": 1},
        {"code": "女", "label": "女", "sort": 2},
    ],
    # 难度
    "difficulty": [
        {"code": "入门", "label": "入门", "sort": 1},
        {"code": "初级", "label": "初级", "sort": 2},
        {"code": "中级", "label": "中级", "sort": 3},
        {"code": "高级", "label": "高级", "sort": 4},
    ],
    # 标注类型
    "annotation_type": [
        {"code": "rect", "label": "矩形框", "sort": 1},
        {"code": "polygon", "label": "多边形", "sort": 2},
        {"code": "pen", "label": "自由画笔", "sort": 3},
    ],
    # 病例分类
    "case_category": [
        {"code": "DR", "label": "糖尿病视网膜病变", "sort": 1},
        {"code": "AMD", "label": "老年性黄斑变性", "sort": 2},
        {"code": "GLAUCOMA", "label": "青光眼", "sort": 3},
        {"code": "HYPERTENSION", "label": "高血压性视网膜病变", "sort": 4},
        {"code": "NORMAL", "label": "正常眼底", "sort": 5},
        {"code": "OTHER", "label": "其它", "sort": 99},
    ],
    # 角色
    "role": [
        {"code": "STUDENT", "label": "学员", "sort": 1},
        {"code": "TEACHER", "label": "带教老师", "sort": 2},
        {"code": "ADMIN", "label": "管理员", "sort": 3},
    ],
    # 公告类型
    "notice_type": [
        {"code": "SYSTEM", "label": "系统通知", "sort": 1},
        {"code": "TRAINING", "label": "培训通知", "sort": 2},
        {"code": "SCREENING", "label": "筛查通知", "sort": 3},
        {"code": "EXAM", "label": "考核通知", "sort": 4},
    ],
}


# ============================================================
#                    医院（静态 mock）
# ============================================================

_HOSPITALS: List[Dict] = [
    {"id": 1, "name": "北京同仁医院",  "level": "三级甲等", "province": "北京", "city": "北京"},
    {"id": 2, "name": "上海第一人民医院", "level": "三级甲等", "province": "上海", "city": "上海"},
    {"id": 3, "name": "中山眼科中心",    "level": "三级甲等", "province": "广东", "city": "广州"},
    {"id": 4, "name": "温州医科大学附属眼视光医院", "level": "三级甲等", "province": "浙江", "city": "温州"},
    {"id": 5, "name": "天津医科大学眼科医院", "level": "三级甲等", "province": "天津", "city": "天津"},
]


def _hospital_name(hospital_id: Optional[int]) -> str:
    if hospital_id is None:
        return ""
    for row in _HOSPITALS:
        if row["id"] == hospital_id:
            return row["name"]
    return ""


def _members_for(db: Session, dept_ids: List[int]) -> Dict[int, List[DepartmentMemberOut]]:
    if not dept_ids:
        return {}
    people = (
        db.query(User)
        .filter(User.department_id.in_(dept_ids))
        .order_by(User.id.asc())
        .all()
    )
    grouped: Dict[int, List[DepartmentMemberOut]] = {}
    for person in people:
        if person.department_id is None:
            continue
        grouped.setdefault(person.department_id, []).append(
            DepartmentMemberOut(
                id=person.id,
                real_name=person.real_name or person.username,
                title=person.title or "",
            )
        )
    return grouped


def _department_out(row: Department, members: Optional[List[DepartmentMemberOut]] = None) -> DepartmentOut:
    return DepartmentOut(
        id=row.id,
        name=row.name,
        hospital_id=row.hospital_id,
        hospital_name=_hospital_name(row.hospital_id),
        members=members or [],
    )

class CommonService:

    # ---------- 系统配置 ----------

    @staticmethod
    def system_config() -> SystemConfigOut:
        return SystemConfigOut(
            app_name=settings.PROJECT_NAME,
            version=settings.PROJECT_VERSION,
            record_no="国械注准 2024-XXXXX",
            terms_url=None,
            privacy_url=None,
            upload_max_mb=settings.SCREENING_MAX_SIZE_MB,
            accept_image_types=["image/jpeg", "image/png", "image/bmp", "image/webp"],
        )

    # ---------- 字典 ----------

    @staticmethod
    def dict_by_type(dict_type: str) -> List[DictItemOut]:
        items = _DICTS.get(dict_type)
        if items is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"字典类型不存在：{dict_type}",
            )
        return [DictItemOut(**it) for it in items]

    @staticmethod
    def dict_batch(types: List[str]) -> Dict[str, List[DictItemOut]]:
        out: Dict[str, List[DictItemOut]] = {}
        for t in types:
            items = _DICTS.get(t, [])
            out[t] = [DictItemOut(**it) for it in items]
        return out

    # ---------- 医院 ----------

    @staticmethod
    def hospitals(keyword: Optional[str] = None) -> List[HospitalOut]:
        rows = _HOSPITALS
        if keyword:
            kw = keyword.strip().lower()
            rows = [
                h for h in rows
                if kw in (h["name"] or "").lower()
                or kw in (h.get("city") or "").lower()
                or kw in (h.get("province") or "").lower()
            ]
        return [HospitalOut(**h) for h in rows]

    # ---------- 科室 ----------

    @staticmethod
    def _assert_hospital_exists(hospital_id: Optional[int]) -> None:
        """医院目前是 _HOSPITALS 里的静态清单，挡一下不存在的 id"""
        if hospital_id is None:
            return
        if not any(h["id"] == hospital_id for h in _HOSPITALS):
            raise HTTPException(400, detail=f"医院不存在：{hospital_id}")

    @staticmethod
    def _assert_code_free(
        db: Session,
        *,
        code: str,
        hospital_id: Optional[int],
        exclude_id: Optional[int] = None,
    ) -> None:
        """
        编码在「同一医院内」唯一。全院通用科室（hospital_id 为 NULL）之间也要
        互不重复 —— 数据库的 UNIQUE 约束对多个 NULL 是放行的，所以这里补一道。
        """
        q = db.query(Department.id).filter(
            Department.code == code,
            Department.hospital_id.is_(None)
            if hospital_id is None
            else Department.hospital_id == hospital_id,
        )
        if exclude_id is not None:
            q = q.filter(Department.id != exclude_id)
        if q.first():
            where = "全院通用科室中" if hospital_id is None else f"该医院（#{hospital_id}）下"
            raise HTTPException(409, detail=f"{where}已存在科室编码：{code}")

    @staticmethod
    def list_departments(
        db: Session,
        hospital_id: Optional[int] = None,
    ) -> List[DepartmentOut]:
        """
        指定医院时只返回这家医院自己的科室。未指定医院的旧数据不混进任何一家，
        否则每家医院都会看到同一份名单。不指定医院时返回全部，供后台总览。
        """
        q = db.query(Department).filter(Department.is_active == True)  # noqa: E712
        if hospital_id is not None:
            q = q.filter(Department.hospital_id == hospital_id)
        rows: List[Department] = q.order_by(
            Department.sort_order.asc(), Department.id.asc()
        ).all()
        grouped = _members_for(db, [row.id for row in rows])
        return [
            _department_out(row, grouped.get(row.id, []))
            for row in rows
        ]

    @staticmethod
    def create_department(db: Session, params: DepartmentSaveParams) -> DepartmentOut:
        if params.hospital_id is None:
            raise HTTPException(400, detail="请选择所属医院")
        CommonService._assert_hospital_exists(params.hospital_id)
        # code 缺省自动生成 DEPT_<id>
        d = Department(
            hospital_id=params.hospital_id,
            code=(params.code or "").strip().upper() or f"DEPT_{int(datetime.now().timestamp())}",
            name=params.name,
            short_name=params.short_name or "",
            leader=params.leader or "",
            phone=params.phone or "",
            sort_order=params.sort_order or 0,
            is_active=bool(params.is_active),
            remark=params.remark or "",
        )
        CommonService._assert_code_free(db, code=d.code, hospital_id=d.hospital_id)
        db.add(d)
        db.commit()
        db.refresh(d)
        return _department_out(d, _members_for(db, [d.id]).get(d.id, []))

    @staticmethod
    def update_department(db: Session, dept_id: int, params: DepartmentSaveParams) -> DepartmentOut:
        d = db.query(Department).filter(Department.id == dept_id).first()
        if not d:
            raise HTTPException(404, detail=f"科室不存在：{dept_id}")
        if params.hospital_id is None:
            raise HTTPException(400, detail="请选择所属医院")
        CommonService._assert_hospital_exists(params.hospital_id)
        new_hospital_id = params.hospital_id
        new_code = params.code.strip().upper() if params.code else d.code
        # 换医院或换编码都可能撞已有科室，一起校验
        if new_code != d.code or new_hospital_id != d.hospital_id:
            CommonService._assert_code_free(
                db, code=new_code, hospital_id=new_hospital_id, exclude_id=d.id
            )
        d.hospital_id = new_hospital_id
        d.code = new_code
        d.name = params.name
        d.short_name = params.short_name or ""
        d.leader = params.leader or ""
        d.phone = params.phone or ""
        d.sort_order = params.sort_order or 0
        d.is_active = bool(params.is_active)
        d.remark = params.remark or ""
        db.commit()
        db.refresh(d)
        return _department_out(d, _members_for(db, [d.id]).get(d.id, []))

    @staticmethod
    def delete_department(db: Session, dept_id: int) -> None:
        d = db.query(Department).filter(Department.id == dept_id).first()
        if not d:
            raise HTTPException(404, detail=f"科室不存在：{dept_id}")
        db.delete(d)
        db.commit()

    # ---------- 全院培训统计 ----------

    @staticmethod
    def training_overview(db: Session) -> TrainingOverviewOut:
        # 学员总数
        student_role = db.query(Role).filter(Role.code == RoleEnum.STUDENT.value).first()
        total_users = (
            db.query(func.count(User.id))
            .filter(User.role_id == (student_role.id if student_role else 0))
            .scalar()
        ) or 0

        total_cases: int = (
            db.query(func.count(TrainingCase.id))
            .filter(TrainingCase.is_published == True)  # noqa: E712
            .scalar()
        ) or 0

        # 这几项原先聚合 TrainingRecord —— 那张表早已没有任何写入方
        # （training_service 里的写入路径前端根本不调），于是总提交数、平均 IoU、
        # 通过率全都恒为 0。学员实际提交落在 PracticeSession（自主练习）和
        # ReadingAnnotation（阅片工作台），这里改成聚合真正在写的两张表。
        practice_records: int = (
            db.query(func.count(PracticeSession.id))
            .filter(PracticeSession.status.in_(_PRACTICE_DONE))
            .scalar()
        ) or 0
        reading_records: int = (
            db.query(func.count(ReadingAnnotation.id))
            .filter(ReadingAnnotation.status.in_(_READING_DONE))
            .scalar()
        ) or 0
        total_records = practice_records + reading_records

        # IoU 与是否通过只有练习记录才有，分母也只能是练习提交数
        avg_iou = db.query(func.avg(PracticeSession.iou_avg)).filter(
            PracticeSession.status.in_(_PRACTICE_DONE),
            PracticeSession.iou_avg >= 0,
        ).scalar()

        passed_cnt: int = (
            db.query(func.count(PracticeSession.id))
            .filter(
                PracticeSession.status.in_(_PRACTICE_DONE),
                PracticeSession.is_passed == True,  # noqa: E712
            )
            .scalar()
        ) or 0
        pass_rate = round(passed_cnt / practice_records, 4) if practice_records else 0.0

        # 难度分布
        diff_rows = (
            db.query(TrainingCase.difficulty, func.count(TrainingCase.id))
            .filter(TrainingCase.is_published == True)  # noqa: E712
            .group_by(TrainingCase.difficulty)
            .all()
        )
        diff_label_map = {"EASY": "入门", "MEDIUM": "中级", "HARD": "高级"}
        by_difficulty = [
            TrainingOverviewItem(label=diff_label_map.get(k, k or "未分类"), value=v)
            for k, v in diff_rows
        ]

        # DR 分级分布
        dr_rows = (
            db.query(TrainingCase.gold_dr_grade, func.count(TrainingCase.id))
            .filter(TrainingCase.is_published == True)  # noqa: E712
            .group_by(TrainingCase.gold_dr_grade)
            .all()
        )
        dr_label_map = {
            "0": "0 级 无 DR",
            "1": "1 级 轻度",
            "2": "2 级 中度",
            "3": "3 级 重度",
            "4": "4 级 PDR",
        }
        by_dr_grade = [
            TrainingOverviewItem(label=dr_label_map.get(k, k or "未知"), value=v)
            for k, v in dr_rows
        ]

        return TrainingOverviewOut(
            total_users=total_users,
            total_cases=total_cases,
            total_records=total_records,
            avg_iou=round(float(avg_iou or 0.0), 4),
            pass_rate=pass_rate,
            by_difficulty=by_difficulty,
            by_dr_grade=by_dr_grade,
        )

    # ---------- 学员学时汇总 ----------

    @staticmethod
    def study_hours(
        db: Session,
        keyword: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> StudyHoursOut:
        student_role = db.query(Role).filter(Role.code == RoleEnum.STUDENT.value).first()
        if not student_role:
            return StudyHoursOut(total=0, list=[])

        uq = db.query(User).filter(User.role_id == student_role.id, User.is_active == True)  # noqa: E712
        if keyword:
            kw = f"%{keyword.strip()}%"
            uq = uq.filter(
                (User.username.like(kw))
                | (User.real_name.like(kw))
                | (User.department.like(kw))
            )

        total = uq.count()
        users: List[User] = (
            uq.order_by(desc(User.id))
            .offset(max(0, (page - 1) * page_size))
            .limit(page_size)
            .all()
        )
        if not users:
            return StudyHoursOut(total=total, list=[])

        user_ids = [u.id for u in users]
        progress = learner_progress(db, user_ids)

        items: List[StudyHoursItem] = []
        for u in users:
            row = progress[u.id]
            secs = row["total_seconds"]
            items.append(StudyHoursItem(
                user_id=u.id,
                username=u.username,
                real_name=u.real_name or "",
                department=u.department or "",
                total_seconds=secs,
                total_hours=round(secs / 3600, 2),
                practice_count=row["practice_count"],
                case_count=row["completed_cases"],
                avg_score=row["avg_score"],
                avg_iou=row["avg_iou"],
            ))

        return StudyHoursOut(total=total, list=items)
