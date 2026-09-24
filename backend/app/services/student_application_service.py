"""
学员开户申请
- 访客提交 → PENDING
- 管理员通过 → 生成 STUDENT + 短信/站内信告知初密
- 管理员驳回 → 短信回传理由
"""

from datetime import datetime
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.models import Department, Role, User, MessageTypeEnum
from app.db.models.student_application import StudentApplication, StudentAppStatusEnum
from app.db.models.user import RoleEnum, UserTypeEnum
from app.schemas.student_application import (
    StudentAppCreate,
    StudentAppOut,
    StudentAppPage,
    StudentAppReview,
    StudentAppStatusOut,
)
from app.services.admin_user_service import _temp_password
from app.services.op_log_service import OpLogService
from app.services.sms_service import send_sms
from app.services.user_message_service import UserMessageService


def _to_out(app: StudentApplication, *, temp_password: Optional[str] = None) -> StudentAppOut:
    username = ""
    if app.created_user is not None:
        username = app.created_user.username
    return StudentAppOut(
        id=app.id,
        real_name=app.real_name,
        phone=app.phone,
        department=app.department or "",
        reason=app.reason or "",
        status=app.status,
        reviewer_id=app.reviewer_id,
        reviewer_name=(
            (app.reviewer.real_name or app.reviewer.username)
            if app.reviewer else ""
        ),
        review_comment=app.review_comment or "",
        reviewed_at=app.reviewed_at,
        created_user_id=app.created_user_id,
        account_username=username or None,
        temp_password=temp_password,
        created_at=app.created_at,
        updated_at=app.updated_at,
    )


def _student_role(db: Session) -> Role:
    role = db.query(Role).filter(Role.code == RoleEnum.STUDENT.value).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="系统未配置学员角色",
        )
    return role


class StudentApplicationService:

    @staticmethod
    def apply(db: Session, params: StudentAppCreate) -> StudentAppOut:
        pending = (
            db.query(StudentApplication)
            .filter(
                StudentApplication.phone == params.phone,
                StudentApplication.status == StudentAppStatusEnum.PENDING.value,
            )
            .first()
        )
        if pending:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该手机号已有待审核申请，请等待审核结果",
            )

        taken = (
            db.query(User)
            .filter(or_(User.username == params.phone, User.phone == params.phone))
            .first()
        )
        if taken:
            role_code = taken.role.code if taken.role else ""
            if role_code == RoleEnum.STUDENT.value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="该手机号已是学员账号，请从学生入口登录",
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该手机号已被其他账号使用，请联系管理员",
            )

        app = StudentApplication(
            real_name=params.real_name,
            phone=params.phone,
            department=params.department,
            reason=params.reason,
            status=StudentAppStatusEnum.PENDING.value,
        )
        db.add(app)
        db.commit()
        db.refresh(app)
        return _to_out(app)

    @staticmethod
    def query_by_phone(db: Session, phone: str) -> StudentAppStatusOut:
        p = (phone or "").strip()
        if not p:
            return StudentAppStatusOut(found=False)
        app = (
            db.query(StudentApplication)
            .filter(StudentApplication.phone == p)
            .order_by(desc(StudentApplication.id))
            .first()
        )
        if not app:
            return StudentAppStatusOut(found=False)
        username = ""
        if app.created_user is not None:
            username = app.created_user.username
        return StudentAppStatusOut(
            found=True,
            status=app.status,
            real_name=app.real_name,
            review_comment=app.review_comment if app.status == StudentAppStatusEnum.REJECTED.value else "",
            account_username=username if app.status == StudentAppStatusEnum.APPROVED.value else "",
            created_at=app.created_at,
            reviewed_at=app.reviewed_at,
        )

    @staticmethod
    def list_apps(
        db: Session,
        *,
        keyword: Optional[str] = None,
        status_code: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> StudentAppPage:
        q = db.query(StudentApplication)
        if keyword:
            kw = f"%{keyword.strip()}%"
            q = q.filter(or_(
                StudentApplication.real_name.like(kw),
                StudentApplication.phone.like(kw),
                StudentApplication.department.like(kw),
                StudentApplication.reason.like(kw),
            ))
        if status_code:
            q = q.filter(StudentApplication.status == status_code)
        total = q.count()
        rows = (
            q.order_by(desc(StudentApplication.id))
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return StudentAppPage(
            total=total,
            page=page,
            page_size=page_size,
            list=[_to_out(r) for r in rows],
        )

    @staticmethod
    def review(
        db: Session,
        *,
        reviewer: User,
        application_id: int,
        params: StudentAppReview,
        ip: str = "",
    ) -> StudentAppOut:
        app = (
            db.query(StudentApplication)
            .filter(StudentApplication.id == application_id)
            .first()
        )
        if not app:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"申请不存在：{application_id}",
            )
        if app.status != StudentAppStatusEnum.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"申请已审核（{app.status}），无法再次操作",
            )

        comment = (params.comment or "").strip()
        if not params.accept and not comment:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="驳回必须填写理由",
            )

        now = datetime.now()
        app.reviewer_id = reviewer.id
        app.reviewed_at = now
        app.review_comment = comment
        temp: Optional[str] = None

        if params.accept:
            role = _student_role(db)
            temp = _temp_password()
            username = app.phone
            if db.query(User).filter(User.username == username).first():
                username = f"s{app.phone}"
            dept_name = (app.department or "").strip()
            dept_id = None
            if dept_name:
                matched = (
                    db.query(Department)
                    .filter(
                        Department.hospital_id.is_(None),
                        Department.is_active.is_(True),
                        Department.name == dept_name,
                    )
                    .all()
                )
                if len(matched) == 1:
                    dept_id = matched[0].id
            user = User(
                username=username,
                password_hash=hash_password(temp),
                real_name=app.real_name,
                phone=app.phone,
                department=dept_name,
                department_id=dept_id,
                role_id=role.id,
                user_type=UserTypeEnum.STUDENT.value,
                is_active=True,
                must_change_password=True,
            )
            db.add(user)
            db.flush()
            app.status = StudentAppStatusEnum.APPROVED.value
            app.created_user_id = user.id

            sms_text = (
                f"【慧眼】学员账号已开通。账号：{username}，初密：{temp}。"
                f"请从学生入口登录后立即修改密码。"
            )
            send_sms(app.phone, sms_text)
            app.notify_sms = sms_text

            UserMessageService.push(
                db,
                user_id=user.id,
                msg_type=MessageTypeEnum.STUDENT_APPLICATION.value,
                title="学员账号已开通",
                content=(
                    f"您的学员开户申请已通过。\n"
                    f"登录账号：{username}\n"
                    f"初始密码：{temp}\n"
                    f"请从「学生入口」登录，首次登录必须改密。"
                    + (f"\n审核备注：{comment}" if comment else "")
                ),
                ref_type="student_application",
                ref_id=app.id,
                commit=False,
            )
            OpLogService.record(
                db, user=reviewer, module="user", action="approve_student_app",
                detail=f"通过开户申请#{app.id} → {username}",
                ip=ip, commit=False,
            )
        else:
            app.status = StudentAppStatusEnum.REJECTED.value
            sms_text = (
                f"【慧眼】学员开户申请未通过。理由：{comment}"
            )
            send_sms(app.phone, sms_text)
            app.notify_sms = sms_text
            OpLogService.record(
                db, user=reviewer, module="user", action="reject_student_app",
                detail=f"驳回开户申请#{app.id} {app.phone}",
                ip=ip, commit=False,
            )

        db.commit()
        db.refresh(app)
        return _to_out(app, temp_password=temp)
