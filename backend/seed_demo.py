"""
演示数据种子脚本
- 往各业务表批量写入可演示数据，便于前端联调
- 幂等：每次运行都会重置（先清空业务数据再写入）；账号/角色不动
- 用法：先 `python init_data.py` 建表与账号，再 `python seed_demo.py`

依赖：admin / teacher / student 三个账号已通过 init_data.py 创建
"""

from datetime import datetime, timedelta
from typing import List

from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import (
    CaseArchiveStatusEnum,
    CaseCategoryEnum,
    CaseDifficultyEnum,
    Department,
    DrGradeEnum,
    EyeSideEnum,
    GenderEnum,
    LearningNote,
    LearningResource,
    Notice,
    NoticeStatusEnum,
    NoticeTypeEnum,
    PracticeModeEnum,
    PracticeSession,
    PracticeStatusEnum,
    ReadingAnnotation,
    ReadingStatusEnum,
    ResourceFavorite,
    ResourceStatusEnum,
    ResourceTypeEnum,
    RiskLevelEnum,
    RoleEnum,
    ScreeningCase,
    ScreeningResult,
    ScreeningStatusEnum,
    TrainingCase,
    User,
)
from app.db.session import SessionLocal, engine


# ============================================================
# 工具
# ============================================================

def _user_id(db: Session, username: str) -> int:
    u = db.query(User).filter(User.username == username).first()
    if not u:
        raise RuntimeError(
            f"账号 {username} 未找到，请先执行 python init_data.py 初始化账号"
        )
    return u.id


def _wipe(db: Session, model, label: str) -> None:
    """清空一个表的全部数据"""
    n = db.query(model).count()
    if n == 0:
        return
    db.query(model).delete()
    db.commit()
    print(f"    - 清空 {label}：{n} 条")


def _ensure_schema() -> None:
    """
    确保所有 ORM 定义的表都存在；新增字段在 SQLite 上不会自动迁移，
    若检测到字段缺失，按需补一次 ALTER TABLE。
    """
    Base.metadata.create_all(bind=engine)

    # SQLite 兼容：补齐 archive_status 字段（若旧库缺失）
    from sqlalchemy import inspect, text
    insp = inspect(engine)
    try:
        cols = {c["name"] for c in insp.get_columns("biz_training_case")}
    except Exception:
        cols = set()
    if cols and "archive_status" not in cols:
        with engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE biz_training_case ADD COLUMN archive_status "
                "VARCHAR(16) NOT NULL DEFAULT 'ACTIVE'"
            ))
        print("    + 已补齐 biz_training_case.archive_status 字段")
    if cols and "is_train_case" not in cols:
        with engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE biz_training_case ADD COLUMN is_train_case "
                "BOOLEAN NOT NULL DEFAULT 0"
            ))
        print("    + 已补齐 biz_training_case.is_train_case 字段")

    # 体检报告确认 / 推送
    try:
        sc_cols = {c["name"] for c in insp.get_columns("biz_screening_case")}
    except Exception:
        sc_cols = set()
    if sc_cols and "report_status" not in sc_cols:
        with engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE biz_screening_case ADD COLUMN report_status "
                "VARCHAR(16) NOT NULL DEFAULT 'pending'"
            ))
        print("    + 已补齐 biz_screening_case.report_status 字段")
    if sc_cols and "report_pdf_path" not in sc_cols:
        with engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE biz_screening_case ADD COLUMN report_pdf_path "
                "VARCHAR(512) NOT NULL DEFAULT ''"
            ))
        print("    + 已补齐 biz_screening_case.report_pdf_path 字段")
    if sc_cols and "patient_user_id" not in sc_cols:
        with engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE biz_screening_case ADD COLUMN patient_user_id "
                "INTEGER NULL"
            ))
        print("    + 已补齐 biz_screening_case.patient_user_id 字段")


def _now(offset_days: int = 0, offset_hours: int = 0) -> datetime:
    return datetime.now() + timedelta(days=offset_days, hours=offset_hours)


# 演示用的眼底图（公网占位图，随便替换）
DEMO_FUNDUS = [
    "https://www.kaggle.com/static/images/site-logo.svg",
]
LOCAL_FUNDUS = [
    "/static/demo/fundus_normal_01.jpg",
    "/static/demo/fundus_dr1_01.jpg",
    "/static/demo/fundus_dr2_01.jpg",
    "/static/demo/fundus_dr3_01.jpg",
    "/static/demo/fundus_dr4_01.jpg",
    "/static/demo/fundus_amd_01.jpg",
    "/static/demo/fundus_glaucoma_01.jpg",
]


# ============================================================
# 种子数据：科室
# ============================================================

DEPT_SEED = [
    ("OPHTH",   "眼科",       "眼科",     "李主任", "010-66662001", 1),
    ("ENDO",    "内分泌科",   "内分泌",   "王主任", "010-66662002", 2),
    ("FAMILY",  "全科医学科", "全科",     "赵主任", "010-66662003", 3),
    ("INFO",    "信息中心",   "信息",     "孙主任", "010-66662099", 99),
]


def seed_departments(db: Session) -> None:
    print("[1] 写入科室 ...")
    _wipe(db, Department, "biz_department")
    for code, name, short, leader, phone, sort_order in DEPT_SEED:
        db.add(Department(
            code=code, name=name, short_name=short,
            leader=leader, phone=phone, sort_order=sort_order,
            is_active=True,
        ))
    db.commit()
    print(f"    + 科室 {len(DEPT_SEED)} 条")


# ============================================================
# 种子数据：实训病例
# ============================================================

TRAINING_CASES = [
    {
        "case_no": "T2026001", "title": "正常眼底（教学示例）",
        "category": CaseCategoryEnum.NORMAL.value,
        "difficulty": CaseDifficultyEnum.EASY.value,
        "patient_age": 28, "patient_gender": "F",
        "clinical_info": "常规体检，无糖尿病史，视力 5.0",
        "image_paths": {"UK": [LOCAL_FUNDUS[0]]},
        "gold_dr_grade": "0",
        "gold_diagnosis": "未见明显眼底异常",
        "gold_lesions": [],
        "gold_annotations": [],
        "teaching_points": "正常眼底特征：视盘界限清晰、动静脉比例约 2:3、黄斑反光锐利。",
        "pass_score": 70,
    },
    {
        "case_no": "T2026002", "title": "轻度 NPDR（DR 1 级）",
        "category": CaseCategoryEnum.DR.value,
        "difficulty": CaseDifficultyEnum.EASY.value,
        "patient_age": 52, "patient_gender": "M",
        "clinical_info": "2 型糖尿病 8 年，HbA1c 7.6，无视力下降",
        "image_paths": {"UK": [LOCAL_FUNDUS[1]]},
        "gold_dr_grade": "1",
        "gold_diagnosis": "轻度非增殖性糖尿病视网膜病变（NPDR），可见少量微动脉瘤",
        "gold_lesions": [{"type": "MA", "count": 4}],
        "gold_annotations": [
            {"id": "g1", "tool": "rect", "label": "微动脉瘤",
             "points": [{"x": 320, "y": 260}, {"x": 350, "y": 290}],
             "color": "#f53f3f", "layer": "gold"}
        ],
        "teaching_points": "DR 1 级关键体征：仅有微动脉瘤（MA），无出血/渗出/IRMA。",
        "pass_score": 60,
    },
    {
        "case_no": "T2026003", "title": "中度 NPDR（DR 2 级）",
        "category": CaseCategoryEnum.DR.value,
        "difficulty": CaseDifficultyEnum.MEDIUM.value,
        "patient_age": 60, "patient_gender": "F",
        "clinical_info": "糖尿病 12 年，自觉视物模糊 3 月",
        "image_paths": {"UK": [LOCAL_FUNDUS[2]]},
        "gold_dr_grade": "2",
        "gold_diagnosis": "中度 NPDR，多发微动脉瘤伴点状出血与硬性渗出",
        "gold_lesions": [
            {"type": "MA", "count": 12},
            {"type": "HM", "count": 5},
            {"type": "HE", "count": 3},
        ],
        "gold_annotations": [
            {"id": "g1", "tool": "rect", "label": "出血",
             "points": [{"x": 280, "y": 320}, {"x": 320, "y": 360}],
             "color": "#f53f3f", "layer": "gold"},
            {"id": "g2", "tool": "rect", "label": "硬渗",
             "points": [{"x": 410, "y": 230}, {"x": 460, "y": 270}],
             "color": "#fadb14", "layer": "gold"},
        ],
        "teaching_points": "DR 2 级：MA 多发，伴点片状出血、硬性渗出，但未见严重 NPDR 体征。",
        "pass_score": 60,
    },
    {
        "case_no": "T2026004", "title": "重度 NPDR（DR 3 级）",
        "category": CaseCategoryEnum.DR.value,
        "difficulty": CaseDifficultyEnum.HARD.value,
        "patient_age": 55, "patient_gender": "M",
        "clinical_info": "糖尿病 18 年，血糖控制不佳，视力下降 6 月",
        "image_paths": {"UK": [LOCAL_FUNDUS[3]]},
        "gold_dr_grade": "3",
        "gold_diagnosis": (
            "重度 NPDR：记录为两个象限静脉串珠、一个象限 IRMA，没有新生血管。"
            "出血没有按四个象限分别计数，不能写成每个象限多于 20 处。"
        ),
        "gold_lesions": [
            {"type": "HM", "count": 24},
            {"type": "VB", "count": 2},
            {"type": "IRMA", "count": 1},
        ],
        "gold_annotations": [
            {"id": "g1", "tool": "rect", "label": "出血",
             "points": [{"x": 200, "y": 220}, {"x": 260, "y": 280}],
             "color": "#f53f3f", "layer": "gold"},
            {"id": "g2", "tool": "rect", "label": "出血",
             "points": [{"x": 480, "y": 320}, {"x": 540, "y": 380}],
             "color": "#f53f3f", "layer": "gold"},
        ],
        "teaching_points": (
            "重度非增殖性糖尿病视网膜病变（重度 NPDR）采用 4-2-1 标准："
            "四个象限中每个象限视网膜内出血都多于 20 处，"
            "或至少两个象限有明确的静脉串珠，"
            "或至少一个象限有明显的视网膜内微血管异常（IRMA）。"
            "三条里满足任何一条，并且没有新生血管，才是重度 NPDR。"
            "本例记录为两个象限静脉串珠和一个象限 IRMA，没有新生血管。"
            "本示例图不作为新生血管（NVD/NVE）教学。"
        ),
        "pass_score": 65,
    },
    {
        "case_no": "T2026005", "title": "增殖性 DR（PDR，DR 4 级）",
        "category": CaseCategoryEnum.DR.value,
        "difficulty": CaseDifficultyEnum.HARD.value,
        "patient_age": 47, "patient_gender": "M",
        "clinical_info": "糖尿病 20 年，视力骤降，玻璃体出血史",
        "image_paths": {"UK": [LOCAL_FUNDUS[4]]},
        "gold_dr_grade": "4",
        "gold_diagnosis": "增殖性糖尿病视网膜病变，可见视盘新生血管（NVD）",
        "gold_lesions": [
            {"type": "NV", "count": 3},
            {"type": "HM", "count": 30},
        ],
        "gold_annotations": [
            {"id": "g1", "tool": "rect", "label": "新生血管",
             "points": [{"x": 340, "y": 180}, {"x": 420, "y": 250}],
             "color": "#722ed1", "layer": "gold"},
        ],
        "teaching_points": "PDR 关键：视盘/视盘外新生血管（NVD/NVE）；建议尽快全视网膜激光或玻切术。",
        "pass_score": 70,
    },
    {
        "case_no": "T2026006", "title": "AMD 干性",
        "category": CaseCategoryEnum.AMD.value,
        "difficulty": CaseDifficultyEnum.MEDIUM.value,
        "patient_age": 71, "patient_gender": "F",
        "clinical_info": "中心视力下降 1 年，无糖尿病史",
        "image_paths": {"OD": [LOCAL_FUNDUS[5]]},
        "gold_dr_grade": "0",
        "gold_diagnosis": "干性年龄相关性黄斑变性（玻璃膜疣）",
        "gold_lesions": [{"type": "Drusen", "count": 6}],
        "gold_annotations": [
            {"id": "g1", "tool": "polygon", "label": "玻璃膜疣",
             "points": [
                 {"x": 360, "y": 360}, {"x": 400, "y": 350},
                 {"x": 420, "y": 380}, {"x": 380, "y": 400},
             ],
             "color": "#fadb14", "layer": "gold"},
        ],
        "teaching_points": "干性 AMD：黄斑区玻璃膜疣、色素紊乱；与 DR 区分关键看血管病变。",
        "pass_score": 60,
    },
    {
        "case_no": "T2026007", "title": "原发性开角型青光眼",
        "category": CaseCategoryEnum.GLAUCOMA.value,
        "difficulty": CaseDifficultyEnum.MEDIUM.value,
        "patient_age": 58, "patient_gender": "M",
        "clinical_info": "眼压偏高、视野缺损，C/D 0.7",
        "image_paths": {"OD": [LOCAL_FUNDUS[6]]},
        "gold_dr_grade": "0",
        "gold_diagnosis": "原发性开角型青光眼，视盘陷凹扩大",
        "gold_lesions": [{"type": "OpticDiskCupping", "count": 1}],
        "gold_annotations": [
            {"id": "g1", "tool": "rect", "label": "视盘陷凹",
             "points": [{"x": 300, "y": 250}, {"x": 400, "y": 350}],
             "color": "#1677ff", "layer": "gold"},
        ],
        "teaching_points": "C/D 比 ≥0.6、神经纤维层缺损 + 视野缺损 + 高眼压 → 提示青光眼。",
        "pass_score": 65,
    },
]


def seed_training_cases(db: Session, teacher_id: int) -> List[int]:
    print("[2] 写入实训病例 ...")
    _wipe(db, TrainingCase, "biz_training_case")
    ids: List[int] = []
    for c in TRAINING_CASES:
        case = TrainingCase(
            case_no=c["case_no"],
            title=c["title"],
            description=c.get("description", ""),
            category=c["category"],
            difficulty=c["difficulty"],
            patient_age=c.get("patient_age"),
            patient_gender=c.get("patient_gender", "U"),
            clinical_info=c.get("clinical_info", ""),
            image_paths=c.get("image_paths", {}),
            gold_dr_grade=c["gold_dr_grade"],
            gold_diagnosis=c["gold_diagnosis"],
            gold_lesions=c.get("gold_lesions", []),
            gold_annotations=c.get("gold_annotations", []),
            gold_heatmap_path="",
            teaching_points=c.get("teaching_points", ""),
            pass_score=c.get("pass_score", 60),
            is_published=True,
            archive_status=CaseArchiveStatusEnum.ACTIVE.value,
            creator_id=teacher_id,
        )
        db.add(case)
        db.flush()
        ids.append(case.id)
    db.commit()
    print(f"    + 实训病例 {len(ids)} 条")
    return ids


# ============================================================
# 种子数据：AI 筛查病例 + 结果
# ============================================================

SCREENING_CASES = [
    {
        "case_no": "P2026001", "patient_name": "张*",
        "patient_id_card": "1101**********0011", "gender": "M", "age": 56,
        "phone": "138****0001",
        "chief_complaint": "右眼视力模糊 2 周",
        "medical_history": "2 型糖尿病 10 年，规律口服降糖药",
        "diabetes_years": 10,
        "image_paths": {"OD": [LOCAL_FUNDUS[2]], "OS": [LOCAL_FUNDUS[1]]},
        "image_count": 2,
        "status": ScreeningStatusEnum.COMPLETED.value,
        "result": {
            "dr_grade": "2", "risk_level": RiskLevelEnum.MEDIUM.value,
            "risk_score": 0.66, "referral_required": True,
            "lesions": [{"type": "MA", "count": 8, "score": 0.91},
                        {"type": "HM", "count": 3, "score": 0.83}],
        },
    },
    {
        "case_no": "P2026002", "patient_name": "李*",
        "patient_id_card": "1101**********0022", "gender": "F", "age": 62,
        "phone": "138****0002",
        "chief_complaint": "双眼视物变形",
        "medical_history": "高血压 15 年，糖尿病 6 年",
        "diabetes_years": 6,
        "image_paths": {"OD": [LOCAL_FUNDUS[3]], "OS": [LOCAL_FUNDUS[2]]},
        "image_count": 2,
        "status": ScreeningStatusEnum.COMPLETED.value,
        "result": {
            "dr_grade": "3", "risk_level": RiskLevelEnum.HIGH.value,
            "risk_score": 0.84, "referral_required": True,
            "lesions": [{"type": "HM", "count": 18, "score": 0.95}],
        },
    },
    {
        "case_no": "P2026003", "patient_name": "王*",
        "patient_id_card": "1101**********0033", "gender": "M", "age": 41,
        "phone": "138****0003",
        "chief_complaint": "常规年度体检",
        "medical_history": "无慢病史",
        "diabetes_years": 0,
        "image_paths": {"UK": [LOCAL_FUNDUS[0]]},
        "image_count": 1,
        "status": ScreeningStatusEnum.COMPLETED.value,
        "result": {
            "dr_grade": "0", "risk_level": RiskLevelEnum.LOW.value,
            "risk_score": 0.05, "referral_required": False,
            "lesions": [],
        },
    },
    {
        "case_no": "P2026004", "patient_name": "陈*",
        "patient_id_card": "1101**********0044", "gender": "F", "age": 68,
        "phone": "138****0004",
        "chief_complaint": "中心视力下降 6 月",
        "medical_history": "无糖尿病",
        "diabetes_years": 0,
        "image_paths": {"OD": [LOCAL_FUNDUS[5]]},
        "image_count": 1,
        "status": ScreeningStatusEnum.PENDING.value,
        "result": None,
    },
    {
        "case_no": "P2026005", "patient_name": "赵*",
        "patient_id_card": "1101**********0055", "gender": "M", "age": 45,
        "phone": "138****0005",
        "chief_complaint": "无症状，新发糖尿病初筛",
        "medical_history": "新诊断 2 型糖尿病 3 月",
        "diabetes_years": 0,
        "image_paths": {"OD": [LOCAL_FUNDUS[1]], "OS": [LOCAL_FUNDUS[0]]},
        "image_count": 2,
        "status": ScreeningStatusEnum.PROCESSING.value,
        "result": None,
    },
]


def seed_screening(db: Session, submit_user_id: int, doctor_id: int) -> None:
    print("[3] 写入筛查病例与结果 ...")
    _wipe(db, ScreeningResult, "biz_screening_result")
    _wipe(db, ScreeningCase, "biz_screening_case")
    ophth = db.query(Department).filter(Department.code == "OPHTH").first()
    dept_id = ophth.id if ophth else None

    for idx, c in enumerate(SCREENING_CASES):
        sc = ScreeningCase(
            case_no=c["case_no"],
            patient_name=c["patient_name"],
            patient_id_card=c["patient_id_card"],
            gender=c["gender"], age=c["age"], phone=c["phone"],
            chief_complaint=c["chief_complaint"],
            medical_history=c["medical_history"],
            diabetes_years=c["diabetes_years"],
            image_paths=c["image_paths"],
            image_count=c["image_count"],
            status=c["status"],
            department_id=dept_id,
            submit_user_id=submit_user_id,
            review_user_id=doctor_id if c["status"] == ScreeningStatusEnum.COMPLETED.value else None,
            submit_at=_now(-idx * 2, -2),
            review_at=_now(-idx * 2, -1) if c["status"] == ScreeningStatusEnum.COMPLETED.value else None,
            remark="",
        )
        db.add(sc)
        db.flush()

        if c["result"]:
            r = c["result"]
            res = ScreeningResult(
                case_id=sc.id,
                eye_side=EyeSideEnum.OU.value,
                model_name="HuiyanFundus-DR",
                model_version="v1.3.2",
                dr_grade=r["dr_grade"],
                has_dme=False,
                risk_level=r["risk_level"],
                risk_score=r["risk_score"],
                referral_required=bool(r["referral_required"]),
                lesions=r.get("lesions", []),
                annotations=[],
                heatmap_path="",
                thumbnail_path=c["image_paths"].get("OD", [""])[0],
                infer_duration_ms=900 + idx * 60,
                inferred_at=_now(-idx * 2, -1),
                doctor_diagnosis=(
                    "AI 与医生定级一致，建议按风险等级随访" if r["dr_grade"] != "0" else "未见异常"
                ),
                doctor_grade=r["dr_grade"],
                doctor_id=doctor_id,
                doctor_at=_now(-idx * 2, -1),
            )
            db.add(res)
    db.commit()
    print(f"    + 筛查病例 {len(SCREENING_CASES)} 条")


# ============================================================
# 种子数据：公告
# ============================================================

NOTICES = [
    {
        "title": "【系统升级】慧眼云 V2.0 教学功能全面上线",
        "summary": "新增自主练习、自动评分、金标准对比、学习笔记等模块",
        "content": "亲爱的医师们，我们很高兴地宣布慧眼云 V2.0 已正式发布。"
                   "新版本带来：1) 自主练习与 IoU 自动评分；2) 公共学习资料中心；"
                   "3) 个人学习笔记，可一键关联当前阅片影像；4) 教师在教学首页点开学员，可看完成病例、得分变化、漏诊误诊和评语。"
                   "祝学习愉快！",
        "notice_type": NoticeTypeEnum.SYSTEM.value,
        "is_top": True,
    },
    {
        "title": "【培训通知】2026 年第二期 DR 阅片标准化培训开班",
        "summary": "面向住培医师 / 全科医师，共 8 课时，配套自主练习",
        "content": "时间：2026-06-01 至 2026-06-30；"
                   "形式：直播课 + 病例库自学 + 自主练习 + 在线考核。"
                   "开班前请完成账号激活并完成 3 例 DR EASY 难度的练习。",
        "notice_type": NoticeTypeEnum.TRAINING.value,
        "is_top": False,
    },
    {
        "title": "【筛查通知】五月份社区糖网筛查总结",
        "summary": "本月共筛查 1280 人，转诊 56 例",
        "content": "本月各社区医院共完成糖网筛查 1280 人次，AI 自动定级耗时平均 0.9s；"
                   "经医师复核后建议转诊 56 例（4.4%），其中 PDR 5 例。",
        "notice_type": NoticeTypeEnum.SCREENING.value,
        "is_top": False,
    },
    {
        "title": "【考核提醒】住培年度阅片考核将于 6 月 15 日启动",
        "summary": "考核内容：10 例随机病例 · 60 分钟内完成",
        "content": "请所有住培医师在 6 月 15 日前完成至少 20 例自主练习，"
                   "并保证近 5 次练习平均得分 ≥ 60 分。",
        "notice_type": NoticeTypeEnum.EXAM.value,
        "visible_roles": "STUDENT",
        "is_top": False,
    },
]


def seed_notices(db: Session, publisher_id: int) -> None:
    print("[4] 写入公告 ...")
    _wipe(db, Notice, "biz_notice")
    for i, n in enumerate(NOTICES):
        db.add(Notice(
            title=n["title"], summary=n["summary"], content=n["content"],
            cover_url="",
            notice_type=n["notice_type"],
            status=NoticeStatusEnum.PUBLISHED.value,
            visible_roles=n.get("visible_roles", ""),
            is_top=bool(n.get("is_top", False)),
            publisher_id=publisher_id,
            publish_at=_now(-i),
            expire_at=None,
            view_count=120 - i * 18,
        ))
    db.commit()
    print(f"    + 公告 {len(NOTICES)} 条")


# ============================================================
# 种子数据：学习资料 / 收藏 / 笔记
# ============================================================

LEARNING_RESOURCES = [
    {
        "title": "DR 国际临床分级标准 2003（ICDR）速记",
        "summary": "5 级分级法、4-2-1 法则、PDR 鉴别要点一图速览",
        "content": "## DR 国际临床分级（ICDR）\n\n"
                   "| 级别 | 名称 | 关键体征 |\n"
                   "|------|------|---------|\n"
                   "| 0 | 无 DR | 无视网膜病变 |\n"
                   "| 1 | 轻度 NPDR | 仅微动脉瘤 |\n"
                   "| 2 | 中度 NPDR | MA + 出血/硬渗 |\n"
                   "| 3 | 重度 NPDR | 4-2-1 标准，且没有新生血管 |\n"
                   "| 4 | PDR | 必须见到新生血管 |\n\n"
                   "重度 NPDR 的 4-2-1 标准：四个象限中每个象限视网膜内出血都多于 20 处，"
                   "或至少两个象限有明确的静脉串珠，"
                   "或至少一个象限有明显的视网膜内微血管异常（IRMA）。"
                   "满足任何一条，并且没有新生血管，才是重度 NPDR。"
                   "没有新生血管不能诊断 PDR。\n",
        "resource_type": ResourceTypeEnum.KNOWLEDGE.value,
        "tags": "DR,分级,4-2-1,ICDR",
    },
    {
        "title": "正常眼底解剖与影像识别要点",
        "summary": "视盘 / 黄斑 / 动静脉 / 神经纤维层的标准影像表现",
        "content": "本节介绍正常眼底的关键标志：视盘、黄斑、动脉/静脉的比例（约 2:3）、神经纤维层。",
        "resource_type": ResourceTypeEnum.KNOWLEDGE.value,
        "tags": "解剖,正常眼底,基础",
    },
    {
        "title": "AMD 干性 vs 湿性：影像鉴别课件",
        "summary": "玻璃膜疣 / 地图样萎缩 / CNV 渗出鉴别要点",
        "content": "干性 AMD：玻璃膜疣、色素紊乱、地图样萎缩；"
                   "湿性 AMD：脉络膜新生血管（CNV）、视网膜下出血、渗出。",
        "resource_type": ResourceTypeEnum.COURSEWARE.value,
        "tags": "AMD,黄斑变性,鉴别诊断",
    },
    {
        "title": "青光眼视盘评估：C/D 比与 ISNT 法则",
        "summary": "视盘陷凹、神经视网膜环、ISNT 法则解读",
        "content": "C/D 比：杯盘比 >0.6 提示异常；ISNT 法则：视盘下方 ≥ 上方 ≥ 鼻侧 ≥ 颞侧。",
        "resource_type": ResourceTypeEnum.COURSEWARE.value,
        "tags": "青光眼,视盘,C/D比,ISNT",
    },
    {
        "title": "教学影像：DR 各级标准范例",
        "summary": "DR 0~4 级各 2 张高清眼底影像范例",
        "content": "请在阅片工作站打开附件影像，对照 ICDR 标准识别关键体征。",
        "resource_type": ResourceTypeEnum.IMAGE_DEMO.value,
        "tags": "DR,影像,范例",
        "file_url": "/static/demo/dr_grades_demo.zip",
        "file_type": "image",
    },
    {
        "title": "病例范本：典型 PDR 案例分析",
        "summary": "55 岁糖尿病 20 年男性，PDR + 玻璃体出血",
        "content": "本病例展示从重度 NPDR 进展为 PDR 的典型过程，重点讲解 NVD/NVE 识别与处理。",
        "resource_type": ResourceTypeEnum.CASE_TEMPLATE.value,
        "tags": "PDR,病例分析,新生血管",
    },
]


def seed_learning(
    db: Session,
    teacher_id: int,
    student_id: int,
    case_ids: List[int],
) -> None:
    print("[5] 写入学习资料 / 收藏 / 笔记 ...")
    _wipe(db, LearningNote, "biz_learning_note")
    _wipe(db, ResourceFavorite, "biz_resource_favorite")
    _wipe(db, LearningResource, "biz_learning_resource")

    res_ids: List[int] = []
    for i, r in enumerate(LEARNING_RESOURCES):
        bind_case = case_ids[i % len(case_ids)] if case_ids else None
        # 病例范本类型才绑定病例
        link_case = bind_case if r["resource_type"] in (
            ResourceTypeEnum.CASE_TEMPLATE.value,
            ResourceTypeEnum.IMAGE_DEMO.value,
        ) else None
        rec = LearningResource(
            title=r["title"],
            summary=r["summary"],
            content=r["content"],
            resource_type=r["resource_type"],
            tags=r["tags"],
            cover_url=r.get("cover_url", ""),
            file_url=r.get("file_url", ""),
            file_type=r.get("file_type", ""),
            case_id=link_case,
            status=ResourceStatusEnum.PUBLISHED.value,
            publisher_id=teacher_id,
            view_count=80 - i * 10,
            favorite_count=0,
        )
        db.add(rec)
        db.flush()
        res_ids.append(rec.id)
    db.commit()
    print(f"    + 学习资料 {len(res_ids)} 条")

    # 学员收藏前 3 份
    fav_resources = res_ids[:3]
    for rid in fav_resources:
        db.add(ResourceFavorite(
            user_id=student_id,
            resource_id=rid,
            label="高频考点",
        ))
        r = db.query(LearningResource).filter(LearningResource.id == rid).first()
        if r:
            r.favorite_count = (r.favorite_count or 0) + 1
    db.commit()
    print(f"    + 学员收藏 {len(fav_resources)} 份")

    # 学员笔记 4 条
    notes = [
        {
            "title": "DR 1 级首次识别心得",
            "content": "今天练习 T2026002，关键是识别 MA。"
                       "MA 通常呈圆形红点，直径 < 125μm，"
                       "与点状出血的区别：MA 边界清晰、形态规则。",
            "tags": "DR,微动脉瘤,练习心得",
            "case_id": case_ids[1] if len(case_ids) > 1 else None,
            "image_index": 0,
            "image_url": LOCAL_FUNDUS[1],
            "resource_id": res_ids[0],
        },
        {
            "title": "4-2-1 法则记忆口诀",
            "content": (
                "重度非增殖性糖尿病视网膜病变（重度 NPDR）的 4-2-1 标准：\n"
                "- 四个象限中每个象限视网膜内出血都多于 20 处\n"
                "- 至少两个象限有明确的静脉串珠\n"
                "- 至少一个象限有明显 IRMA\n"
                "满足任何一条，并且没有新生血管，才是重度 NPDR。"
                "没有新生血管不能诊断 PDR。"
            ),
            "tags": "DR3,4-2-1,口诀",
            "case_id": case_ids[3] if len(case_ids) > 3 else None,
            "image_index": 0,
            "image_url": LOCAL_FUNDUS[3],
            "resource_id": res_ids[0],
        },
        {
            "title": "PDR 与重度 NPDR 鉴别要点",
            "content": "PDR 必须有新生血管（NVD/NVE），而重度 NPDR 没有。"
                       "今天遇到 T2026005 这个案例，视盘旁明显新生血管，建议尽快激光。",
            "tags": "PDR,鉴别,新生血管",
            "case_id": case_ids[4] if len(case_ids) > 4 else None,
            "image_index": 0,
            "image_url": LOCAL_FUNDUS[4],
        },
        {
            "title": "干性 AMD 影像复盘",
            "content": "T2026006 这例的关键是黄斑区玻璃膜疣，要与糖网的硬性渗出区分："
                       "玻璃膜疣多位于黄斑、边界模糊；硬渗多沿血管分布、边界锐利。",
            "tags": "AMD,玻璃膜疣,鉴别",
            "case_id": case_ids[5] if len(case_ids) > 5 else None,
            "image_index": 0,
            "image_url": LOCAL_FUNDUS[5],
        },
    ]
    for n in notes:
        db.add(LearningNote(
            user_id=student_id,
            title=n["title"],
            content=n["content"],
            tags=n["tags"],
            case_id=n["case_id"],
            image_index=n.get("image_index", -1),
            image_url=n.get("image_url", ""),
            resource_id=n.get("resource_id"),
        ))
    db.commit()
    print(f"    + 学习笔记 {len(notes)} 条")


# ============================================================
# 种子数据：阅片标注 / 自主练习
# ============================================================

def seed_reading_and_practice(
    db: Session,
    student_id: int,
    teacher_id: int,
    case_ids: List[int],
) -> None:
    print("[6] 写入阅片标注与练习记录 ...")
    _wipe(db, PracticeSession, "biz_practice_session")
    _wipe(db, ReadingAnnotation, "biz_reading_annotation")

    if len(case_ids) < 3:
        print("    (info) 实训病例不足 3 条，跳过")
        return

    # 一份学员阅片草稿
    db.add(ReadingAnnotation(
        case_id=case_ids[1],
        user_id=student_id,
        image_index=0,
        image_url=LOCAL_FUNDUS[1],
        viewport={"scale": 1.2, "x": 0, "y": 0, "ww": 255, "wl": 127, "invert": False},
        annotations=[
            {"id": "a1", "tool": "rect", "label": "微动脉瘤",
             "points": [{"x": 318, "y": 258}, {"x": 348, "y": 288}],
             "color": "#f53f3f", "layer": "primary"}
        ],
        measurements=[],
        layers={"primary": True, "heatmap": False, "gold": False, "my": True},
        status=ReadingStatusEnum.DRAFT.value,
        note="先标了一处疑似 MA，待复核",
    ))

    # 一份学员阅片已提交
    db.add(ReadingAnnotation(
        case_id=case_ids[2],
        user_id=student_id,
        image_index=0,
        image_url=LOCAL_FUNDUS[2],
        viewport={"scale": 1.0, "x": 0, "y": 0, "ww": 255, "wl": 127, "invert": False},
        annotations=[
            {"id": "a1", "tool": "rect", "label": "出血",
             "points": [{"x": 280, "y": 320}, {"x": 320, "y": 360}],
             "color": "#f53f3f", "layer": "primary"},
            {"id": "a2", "tool": "rect", "label": "硬渗",
             "points": [{"x": 410, "y": 230}, {"x": 460, "y": 270}],
             "color": "#fadb14", "layer": "primary"},
        ],
        measurements=[],
        layers={"primary": True, "heatmap": False, "gold": True, "my": True},
        status=ReadingStatusEnum.SUBMITTED.value,
        note="按 ICDR 标准定为 DR 2 级",
    ))
    db.commit()
    print("    + 阅片标注 2 条（草稿 + 已提交）")

    # 三条自主练习记录：通过 / 未通过 / 草稿
    sessions = [
        {
            "case_idx": 1,  # T2026002 DR1
            "status": PracticeStatusEnum.SUBMITTED.value,
            "student_dr_grade": "1",
            "student_diagnosis": "轻度 NPDR，可见微动脉瘤",
            "annotations": [
                {"id": "p1", "tool": "rect", "label": "微动脉瘤",
                 "points": [{"x": 322, "y": 262}, {"x": 348, "y": 288}],
                 "color": "#f53f3f", "layer": "primary"}
            ],
            "score_total": 86.5, "score_grade": 100, "score_annotation": 78,
            "score_diagnosis": 90, "iou_avg": 0.82, "accuracy": 1.0,
            "grade_match": True, "is_passed": True,
            "missed_count": 0, "false_positive_count": 0,
            "error_points": [],
            "suggestion": "完成度优秀，继续保持对 MA 的敏锐识别。",
            "duration_seconds": 320,
        },
        {
            "case_idx": 3,  # T2026004 DR3
            "status": PracticeStatusEnum.SUBMITTED.value,
            "student_dr_grade": "2",  # 错判（金标准 3 级）
            "student_diagnosis": "中度 NPDR，多处出血",
            "annotations": [
                {"id": "p1", "tool": "rect", "label": "出血",
                 "points": [{"x": 200, "y": 220}, {"x": 260, "y": 280}],
                 "color": "#f53f3f", "layer": "primary"},
            ],
            "score_total": 42.0, "score_grade": 75, "score_annotation": 32,
            "score_diagnosis": 40, "iou_avg": 0.55, "accuracy": 0.5,
            "grade_match": False, "is_passed": False,
            "missed_count": 2, "false_positive_count": 0,
            "error_points": [
                {"type": "missed", "label": "新生血管",
                 "expectedLabel": "新生血管",
                 "iou": None,
                 "point": {"x": 360, "y": 200},
                 "note": "漏掉了视盘旁的新生血管，是 PDR 的关键证据"},
                {"type": "missed", "label": "出血",
                 "expectedLabel": "出血",
                 "iou": None,
                 "point": {"x": 480, "y": 320},
                 "note": "漏掉了下方象限的点片状出血"},
            ],
            "suggestion": "建议按 4-2-1 标准复习重度 NPDR：每个象限出血多于 20 处，或两个象限明确静脉串珠，或一个象限明显 IRMA，并且没有新生血管。",
            "duration_seconds": 540,
        },
        {
            "case_idx": 5,  # T2026006 AMD
            "status": PracticeStatusEnum.DRAFT.value,
            "student_dr_grade": "",
            "student_diagnosis": "",
            "annotations": [],
            "score_total": 0, "score_grade": 0, "score_annotation": 0,
            "score_diagnosis": 0, "iou_avg": 0, "accuracy": 0,
            "grade_match": False, "is_passed": False,
            "missed_count": 0, "false_positive_count": 0,
            "error_points": [],
            "suggestion": "",
            "duration_seconds": 0,
        },
    ]

    for i, s in enumerate(sessions):
        idx = s["case_idx"]
        if idx >= len(case_ids):
            continue
        ps = PracticeSession(
            user_id=student_id,
            case_id=case_ids[idx],
            mode=PracticeModeEnum.SELECTED.value,
            status=s["status"],
            student_dr_grade=s["student_dr_grade"],
            student_diagnosis=s["student_diagnosis"],
            student_annotations=s["annotations"],
            student_measurements=[],
            viewport_snapshot={"scale": 1, "x": 0, "y": 0, "ww": 255, "wl": 127},
            score_total=s["score_total"],
            score_grade=s["score_grade"],
            score_annotation=s["score_annotation"],
            score_diagnosis=s["score_diagnosis"],
            iou_avg=s["iou_avg"],
            accuracy=s["accuracy"],
            missed_count=s["missed_count"],
            false_positive_count=s["false_positive_count"],
            grade_match=1 if s["grade_match"] else 0,
            is_passed=1 if s["is_passed"] else 0,
            error_points=s["error_points"],
            suggestion=s["suggestion"],
            started_at=_now(-i, -1),
            submitted_at=(
                _now(-i)
                if s["status"] != PracticeStatusEnum.DRAFT.value
                else None
            ),
            duration_seconds=s["duration_seconds"],
            teacher_comment=(
                "标注规范、思路清晰，继续保持。" if s["is_passed"] else ""
            ),
            teacher_id=teacher_id if s["is_passed"] else None,
        )
        db.add(ps)
    db.commit()
    print(f"    + 练习记录 {len(sessions)} 条（含通过/未通过/草稿）")


# ============================================================
# 主入口
# ============================================================

def main() -> None:
    print(f"[{datetime.now()}] 开始写入演示数据 ...\n")
    print("[0] 同步表结构 ...")
    _ensure_schema()
    db: Session = SessionLocal()
    try:
        admin_id = _user_id(db, "admin")
        teacher_id = _user_id(db, "teacher")
        student_id = _user_id(db, "student")

        seed_departments(db)
        case_ids = seed_training_cases(db, teacher_id)
        seed_screening(db, submit_user_id=teacher_id, doctor_id=teacher_id)
        seed_notices(db, publisher_id=admin_id)
        seed_learning(db, teacher_id, student_id, case_ids)
        seed_reading_and_practice(db, student_id, teacher_id, case_ids)

        print(f"\n[{datetime.now()}] [OK] 演示数据写入完成")
        print("\n建议联调路径：")
        print("  - 学员 student / Huiyan@123  -> 病例库 / 自主练习 / 学习资料 / 我的笔记")
        print("  - 教师 teacher / Huiyan@123  -> 资料管理 / 全班级统计 / 教师点评")
        print("  - 管理员 admin / Admin@123   -> 全量管理后台")
    except Exception as e:
        db.rollback()
        print(f"[FAIL] 写入失败：{e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
