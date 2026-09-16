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
from sqlalchemy import desc, func, or_
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
from app.schemas.common import (
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


# ============================================================
#                    Service
# ============================================================

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
        指定医院时，返回「该医院的科室 + 全院通用科室」；不指定时返回全部。

        原先无论选哪家医院都返回同一份全局清单（测试报告：在 ID 2 的医院建的
        科室，切到别的医院也看得到）。
        """
        q = db.query(Department).filter(Department.is_active == True)  # noqa: E712
        if hospital_id is not None:
            q = q.filter(
                or_(
                    Department.hospital_id == hospital_id,
                    Department.hospital_id.is_(None),
                )
            )
        rows: List[Department] = q.order_by(
            Department.sort_order.asc(), Department.id.asc()
        ).all()
        return [
            DepartmentOut(id=r.id, name=r.name, hospital_id=r.hospital_id)
            for r in rows
        ]

    @staticmethod
    def create_department(db: Session, params: DepartmentSaveParams) -> DepartmentOut:
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
        return DepartmentOut(id=d.id, name=d.name, hospital_id=d.hospital_id)

    @staticmethod
    def update_department(db: Session, dept_id: int, params: DepartmentSaveParams) -> DepartmentOut:
        d = db.query(Department).filter(Department.id == dept_id).first()
        if not d:
            raise HTTPException(404, detail=f"科室不存在：{dept_id}")
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
        return DepartmentOut(id=d.id, name=d.name, hospital_id=d.hospital_id)

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
            PracticeSession.status.in_(_PRACTICE_DONE)
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

        # 原先聚合的 TrainingRecord 没有任何写入方，三列恒为 0
        #（用户测试报告：「学员页面显示已有练习和提交记录，但管理页面显示完成病例为 0」）。
        # 学时与 IoU 只有练习记录才有这两个字段；完成病例则要把阅片提交也算进来，
        # 否则学员在阅片工作台交的那些又会漏掉 —— 两张表的 case_id 都指向
        # biz_training_case.id，可以直接按病例去重取并集。
        agg_rows = (
            db.query(
                PracticeSession.user_id,
                func.coalesce(func.sum(PracticeSession.duration_seconds), 0),
                func.coalesce(func.avg(PracticeSession.iou_avg), 0),
            )
            .filter(
                PracticeSession.user_id.in_(user_ids),
                PracticeSession.status.in_(_PRACTICE_DONE),
            )
            .group_by(PracticeSession.user_id)
            .all()
        )
        stat_map = {
            uid: (int(secs or 0), float(avg or 0.0))
            for uid, secs, avg in agg_rows
        }

        # 完成病例 = 练习已提交 ∪ 阅片已提交，按 (user, case) 去重
        done_pairs: set = set()
        for model, done_status in (
            (PracticeSession, _PRACTICE_DONE),
            (ReadingAnnotation, _READING_DONE),
        ):
            rows = (
                db.query(model.user_id, model.case_id)
                .filter(model.user_id.in_(user_ids), model.status.in_(done_status))
                .distinct()
                .all()
            )
            done_pairs.update(rows)

        case_count_map: Dict[int, int] = {}
        for uid, _case_id in done_pairs:
            case_count_map[uid] = case_count_map.get(uid, 0) + 1

        items: List[StudyHoursItem] = []
        for u in users:
            secs, avg_iou = stat_map.get(u.id, (0, 0.0))
            case_cnt = case_count_map.get(u.id, 0)
            items.append(StudyHoursItem(
                user_id=u.id,
                username=u.username,
                real_name=u.real_name or "",
                department=u.department or "",
                total_seconds=secs,
                total_hours=round(secs / 3600, 2),
                case_count=case_cnt,
                avg_iou=round(avg_iou, 4),
            ))

        return StudyHoursOut(total=total, list=items)
