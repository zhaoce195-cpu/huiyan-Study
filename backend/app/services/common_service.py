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
    RecordStatusEnum,
    Role,
    RoleEnum,
    TrainingCase,
    TrainingRecord,
    User,
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
    def list_departments(
        db: Session,
        hospital_id: Optional[int] = None,  # 当前未做医院-科室关联，预留
    ) -> List[DepartmentOut]:
        rows: List[Department] = (
            db.query(Department)
            .filter(Department.is_active == True)  # noqa: E712
            .order_by(Department.sort_order.asc(), Department.id.asc())
            .all()
        )
        return [
            DepartmentOut(id=r.id, name=r.name, hospital_id=hospital_id)
            for r in rows
        ]

    @staticmethod
    def create_department(db: Session, params: DepartmentSaveParams) -> DepartmentOut:
        # code 缺省自动生成 DEPT_<id>
        d = Department(
            code=(params.code or "").strip().upper() or f"DEPT_{int(datetime.now().timestamp())}",
            name=params.name,
            short_name=params.short_name or "",
            leader=params.leader or "",
            phone=params.phone or "",
            sort_order=params.sort_order or 0,
            is_active=bool(params.is_active),
            remark=params.remark or "",
        )
        # 唯一性
        if db.query(Department).filter(Department.code == d.code).first():
            raise HTTPException(409, detail=f"科室编码已存在：{d.code}")
        db.add(d)
        db.commit()
        db.refresh(d)
        return DepartmentOut(id=d.id, name=d.name)

    @staticmethod
    def update_department(db: Session, dept_id: int, params: DepartmentSaveParams) -> DepartmentOut:
        d = db.query(Department).filter(Department.id == dept_id).first()
        if not d:
            raise HTTPException(404, detail=f"科室不存在：{dept_id}")
        if params.code:
            new_code = params.code.strip().upper()
            if new_code != d.code and db.query(Department).filter(Department.code == new_code).first():
                raise HTTPException(409, detail=f"科室编码已存在：{new_code}")
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
        return DepartmentOut(id=d.id, name=d.name)

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

        total_records: int = (
            db.query(func.count(TrainingRecord.id))
            .filter(TrainingRecord.status != RecordStatusEnum.DRAFT.value)
            .scalar()
        ) or 0

        avg_iou = db.query(func.avg(TrainingRecord.iou_avg)).filter(
            TrainingRecord.status != RecordStatusEnum.DRAFT.value
        ).scalar()

        passed_cnt: int = (
            db.query(func.count(TrainingRecord.id))
            .filter(TrainingRecord.is_passed == 1)
            .scalar()
        ) or 0
        pass_rate = round(passed_cnt / total_records, 4) if total_records else 0.0

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

        # 一次性聚合
        agg_rows = (
            db.query(
                TrainingRecord.user_id,
                func.coalesce(func.sum(TrainingRecord.duration_seconds), 0),
                func.count(func.distinct(TrainingRecord.case_id)),
                func.coalesce(func.avg(TrainingRecord.iou_avg), 0),
            )
            .filter(TrainingRecord.user_id.in_(user_ids))
            .group_by(TrainingRecord.user_id)
            .all()
        )
        stat_map = {
            uid: (int(secs or 0), int(case_cnt or 0), float(avg or 0.0))
            for uid, secs, case_cnt, avg in agg_rows
        }

        items: List[StudyHoursItem] = []
        for u in users:
            secs, case_cnt, avg_iou = stat_map.get(u.id, (0, 0, 0.0))
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
