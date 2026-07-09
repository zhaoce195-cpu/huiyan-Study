"""
病患手机号注册 + 报告查询 业务层
- 短信验证码（模拟，进程内存）
- 注册：同一手机号唯一、自动创建 PATIENT 角色
- 我的报告：通过手机号关联 ScreeningCase，仅返回当前用户的病例
"""

import threading
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.db.models import (
    Role,
    RoleEnum,
    ScreeningCase,
    ScreeningResult,
    ScreeningStatusEnum,
    User,
    UserSetting,
    UserTypeEnum,
)
from app.schemas.patient import (
    BindCaseParams,
    PatientReportItem,
    PatientReportPage,
    RegisterParams,
    SendCodeParams,
    SendCodeResult,
)


# ====================== 模拟验证码（进程内）======================
# 真实生产环境应替换为短信网关 + Redis
_CODE_TTL_SECONDS = 300
_FIXED_DEMO_CODE = "1234"
_code_lock = threading.Lock()
_code_store: Dict[str, Tuple[str, float]] = {}  # phone -> (code, expire_ts)


def _save_code(phone: str, code: str) -> None:
    with _code_lock:
        _code_store[phone] = (code, time.time() + _CODE_TTL_SECONDS)


def _verify_code(phone: str, code: str) -> bool:
    with _code_lock:
        rec = _code_store.get(phone)
        if not rec:
            return False
        saved_code, expire_ts = rec
        if time.time() > expire_ts:
            _code_store.pop(phone, None)
            return False
        ok = saved_code == code
        if ok:
            _code_store.pop(phone, None)
        return ok


# ====================== 字典 ======================

_STATUS_TEXT = {
    "PENDING": "待筛查",
    "PROCESSING": "AI 推理中",
    "COMPLETED": "已完成",
    "REVIEWED": "医生已复核",
    "FAILED": "失败/异常",
}

_DR_GRADE_TEXT = {
    "0": "0 级 无 DR",
    "1": "1 级 轻度 NPDR",
    "2": "2 级 中度 NPDR",
    "3": "3 级 重度 NPDR",
    "4": "4 级 PDR",
}

_RISK_TEXT = {
    "LOW": "低风险",
    "MEDIUM": "中等风险",
    "HIGH": "高风险",
    "URGENT": "紧急",
}


# ====================== Service ======================

class PatientService:

    # ---------- 短信验证码 ----------

    @staticmethod
    def send_code(params: SendCodeParams) -> SendCodeResult:
        # 模拟环境固定返回 1234；如需随机：random.randint(1000,9999)
        code = _FIXED_DEMO_CODE
        _save_code(params.phone, code)
        return SendCodeResult(
            phone=params.phone,
            code=code,
            expires_in=_CODE_TTL_SECONDS,
        )

    # ---------- 注册 ----------

    @staticmethod
    def _ensure_patient_role(db: Session) -> Role:
        role = (
            db.query(Role)
            .filter(Role.code == RoleEnum.PATIENT.value)
            .first()
        )
        if role:
            return role
        role = Role(
            code=RoleEnum.PATIENT.value,
            name="体检病患",
            remark="体检病患账号：仅可查看本人体检报告",
        )
        db.add(role)
        db.commit()
        db.refresh(role)
        return role

    @staticmethod
    def register(db: Session, params: RegisterParams) -> Dict[str, str]:
        # 1) 验证码
        if not _verify_code(params.phone, params.code):
            raise HTTPException(400, detail="短信验证码错误或已过期")

        # 2) 唯一性（同时校验 username 和 phone）
        existing_phone = (
            db.query(User).filter(User.phone == params.phone).first()
        )
        if existing_phone:
            raise HTTPException(409, detail="该手机号已注册")
        existing_username = (
            db.query(User).filter(User.username == params.phone).first()
        )
        if existing_username:
            raise HTTPException(409, detail="该手机号已注册")

        # 3) 角色
        role = PatientService._ensure_patient_role(db)

        # 4) 落库
        user = User(
            username=params.phone,
            password_hash=hash_password(params.password),
            real_name=params.real_name or "",
            phone=params.phone,
            role_id=role.id,
            user_type=UserTypeEnum.PATIENT.value,
            is_active=True,
        )
        user.setting = UserSetting(user_id=0)
        db.add(user)
        db.commit()
        db.refresh(user)

        # 5) 直接签发 token，前端注册成功可立即登录或返回登录页
        token, expire_at = create_access_token(
            subject=user.id,
            extra={"username": user.username, "role": role.code},
        )
        return {
            "userId": str(user.id),
            "username": user.username,
            "phone": user.phone,
            "token": token,
            "expiresAt": expire_at.isoformat(),
        }

    # ---------- 病例绑定（医生 / 管理员） ----------

    @staticmethod
    def bind_case(db: Session, user: User, params: BindCaseParams) -> Dict[str, str]:
        # 仅 ADMIN/TEACHER 可调
        role_code = user.role.code if user.role else ""
        if role_code not in (RoleEnum.ADMIN.value, RoleEnum.TEACHER.value):
            raise HTTPException(403, detail="无权绑定病例手机号")

        case = (
            db.query(ScreeningCase)
            .filter(ScreeningCase.id == params.case_id)
            .first()
        )
        if not case:
            raise HTTPException(404, detail=f"病例不存在：{params.case_id}")

        case.patient_phone = params.patient_phone or ""
        # 如果原 phone 字段为空，同步填充以便联系
        if not case.phone and params.patient_phone:
            case.phone = params.patient_phone
        db.commit()
        return {
            "caseId": str(case.id),
            "patientPhone": case.patient_phone,
        }

    # ---------- 我的报告 ----------

    @staticmethod
    def _to_report_item(
        case: ScreeningCase, latest: Optional[ScreeningResult],
    ) -> PatientReportItem:
        images: List[str] = []
        if case.image_paths:
            for v in case.image_paths.values():
                if isinstance(v, list):
                    images.extend(v)
        doctor_name = ""
        if latest and latest.doctor:
            doctor_name = (
                latest.doctor.real_name or latest.doctor.username or ""
            )

        report_status = (getattr(case, "report_status", "") or "pending").lower()
        report_pdf_path = getattr(case, "report_pdf_path", "") or ""
        pdf_available = report_status == "confirmed" and bool(report_pdf_path)
        # 病患通过统一接口取 PDF（不暴露物理路径）
        report_pdf_url = (
            f"/api/patient/report-pdf/{case.id}" if pdf_available else ""
        )

        return PatientReportItem(
            case_id=case.id,
            case_no=case.case_no,
            patient_name=case.patient_name or "",
            gender=case.gender or "",
            age=case.age,
            chief_complaint=case.chief_complaint or "",
            medical_history=case.medical_history or "",
            images=images,
            image_count=case.image_count or len(images),
            status=case.status,
            status_text=_STATUS_TEXT.get(case.status, case.status),
            dr_grade=(latest.dr_grade if latest else ""),
            dr_grade_text=(
                _DR_GRADE_TEXT.get(latest.dr_grade, latest.dr_grade)
                if latest else ""
            ),
            risk_level=(latest.risk_level if latest else ""),
            risk_level_text=(
                _RISK_TEXT.get(latest.risk_level, latest.risk_level)
                if latest else ""
            ),
            risk_score=(latest.risk_score if latest else 0.0),
            referral_required=bool(latest.referral_required) if latest else False,
            lesions=(latest.lesions if latest and latest.lesions else []),
            doctor_diagnosis=(latest.doctor_diagnosis if latest else ""),
            doctor_grade=(latest.doctor_grade if latest else ""),
            doctor_name=doctor_name,
            submit_at=case.submit_at,
            review_at=case.review_at,
            inferred_at=(latest.inferred_at if latest else None),
            created_at=case.created_at,
            report_status=report_status,
            report_pdf_url=report_pdf_url,
            pdf_available=pdf_available,
        )

    @staticmethod
    def my_reports(
        db: Session, user: User,
        page: int = 1, page_size: int = 20,
        status: Optional[str] = None,
    ) -> PatientReportPage:
        if not user.phone:
            return PatientReportPage(total=0, page=page, page_size=page_size, list=[])

        q = db.query(ScreeningCase).filter(
            ScreeningCase.patient_phone == user.phone
        )
        if status:
            q = q.filter(ScreeningCase.status == status)

        total = q.count()
        rows: List[ScreeningCase] = (
            q.order_by(desc(ScreeningCase.id))
            .offset(max(0, (page - 1) * page_size))
            .limit(page_size)
            .all()
        )

        # 取每例的最新结果（医生覆盖优先）
        items: List[PatientReportItem] = []
        for c in rows:
            latest = (
                db.query(ScreeningResult)
                .filter(ScreeningResult.case_id == c.id)
                .order_by(desc(ScreeningResult.id))
                .first()
            )
            items.append(PatientService._to_report_item(c, latest))

        return PatientReportPage(
            total=total, page=page, page_size=page_size, list=items,
        )

    @staticmethod
    def my_report_detail(db: Session, user: User, case_id: int) -> PatientReportItem:
        case = (
            db.query(ScreeningCase)
            .filter(ScreeningCase.id == case_id)
            .first()
        )
        if not case:
            raise HTTPException(404, detail="报告不存在")
        if not user.phone or case.patient_phone != user.phone:
            raise HTTPException(403, detail="该报告不属于当前账号，无权查看")
        latest = (
            db.query(ScreeningResult)
            .filter(ScreeningResult.case_id == case.id)
            .order_by(desc(ScreeningResult.id))
            .first()
        )
        return PatientService._to_report_item(case, latest)


__all__ = ["PatientService"]
