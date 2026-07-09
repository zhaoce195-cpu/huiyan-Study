"""
机构 / 申请业务层
- 普通用户（PATIENT）通过 apply() 提交申请
- 管理员通过 review() 审核（接受 / 驳回），事务内 push UserMessage
- list_orgs() 给申请下拉用；list_applications() 给后台审核列表用
- 通过同事务把 User.department 写为机构名（已批准时），保留原 schema 不动
"""

from datetime import datetime
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from app.db.models import (
    AppStatusEnum,
    MessageTypeEnum,
    Organization,
    OrganizationApplication,
    User,
)
from app.schemas.organization import (
    OrgApplicationCreate,
    OrgApplicationOut,
    OrgApplicationPage,
    OrgApplicationReview,
    OrganizationOut,
)
from app.services.user_message_service import UserMessageService


def _org_to_out(o: Organization) -> OrganizationOut:
    return OrganizationOut(
        id=o.id,
        name=o.name,
        code=o.code or "",
        category=o.category or "",
        address=o.address or "",
        contact=o.contact or "",
        phone=o.phone or "",
        description=o.description or "",
        is_active=bool(o.is_active),
    )


def _app_to_out(app: OrganizationApplication) -> OrgApplicationOut:
    applicant_name = ""
    applicant_phone = ""
    if app.applicant is not None:
        applicant_name = app.applicant.real_name or app.applicant.username or ""
        applicant_phone = app.applicant.phone or ""
    organization_name = app.organization.name if app.organization is not None else ""
    reviewer_name = ""
    if app.reviewer is not None:
        reviewer_name = app.reviewer.real_name or app.reviewer.username or ""

    return OrgApplicationOut(
        id=app.id,
        applicant_id=app.applicant_id,
        applicant_name=applicant_name,
        applicant_phone=applicant_phone,
        organization_id=app.organization_id,
        organization_name=organization_name,
        reason=app.reason or "",
        status=app.status,  # type: ignore[arg-type]
        reviewer_id=app.reviewer_id,
        reviewer_name=reviewer_name,
        review_comment=app.review_comment or "",
        reviewed_at=app.reviewed_at,
        created_at=app.created_at,
        updated_at=app.updated_at,
    )


class OrganizationService:

    # ========== 机构列表（给申请下拉用） ==========

    @staticmethod
    def list_orgs(db: Session, *, keyword: Optional[str] = None) -> List[OrganizationOut]:
        q = db.query(Organization).filter(Organization.is_active == True)  # noqa: E712
        if keyword:
            kw = f"%{keyword.strip()}%"
            q = q.filter(or_(Organization.name.like(kw), Organization.code.like(kw)))
        rows = q.order_by(Organization.id.asc()).all()
        return [_org_to_out(o) for o in rows]

    # ========== 申请 ==========

    @staticmethod
    def apply(
        db: Session,
        *,
        user: User,
        params: OrgApplicationCreate,
    ) -> OrgApplicationOut:
        """普通用户提交「加入机构」申请。同一用户对同一机构存在 PENDING 时不可重复提交。"""
        org = (
            db.query(Organization)
            .filter(
                Organization.id == params.organization_id,
                Organization.is_active == True,  # noqa: E712
            )
            .first()
        )
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="机构不存在或已停用",
            )

        existing = (
            db.query(OrganizationApplication)
            .filter(
                OrganizationApplication.applicant_id == user.id,
                OrganizationApplication.organization_id == org.id,
                OrganizationApplication.status == AppStatusEnum.PENDING.value,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="该机构已存在待审核的申请，请耐心等待审核结果",
            )

        app = OrganizationApplication(
            applicant_id=user.id,
            organization_id=org.id,
            reason=(params.reason or "").strip(),
            status=AppStatusEnum.PENDING.value,
        )
        db.add(app)
        db.commit()
        db.refresh(app)
        return _app_to_out(app)

    @staticmethod
    def list_my_applications(
        db: Session,
        *,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> OrgApplicationPage:
        q = db.query(OrganizationApplication).filter(
            OrganizationApplication.applicant_id == user_id
        )
        total = q.count()
        rows = (
            q.order_by(desc(OrganizationApplication.id))
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return OrgApplicationPage(
            total=total,
            page=page,
            page_size=page_size,
            list=[_app_to_out(r) for r in rows],
        )

    @staticmethod
    def list_for_admin(
        db: Session,
        *,
        keyword: Optional[str] = None,
        status_filter: Optional[str] = None,
        organization_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> OrgApplicationPage:
        q = db.query(OrganizationApplication)

        if status_filter:
            q = q.filter(OrganizationApplication.status == status_filter)
        if organization_id:
            q = q.filter(OrganizationApplication.organization_id == organization_id)
        if keyword:
            kw = f"%{keyword.strip()}%"
            q = (
                q.outerjoin(User, User.id == OrganizationApplication.applicant_id)
                .outerjoin(
                    Organization,
                    Organization.id == OrganizationApplication.organization_id,
                )
                .filter(
                    or_(
                        User.real_name.like(kw),
                        User.username.like(kw),
                        User.phone.like(kw),
                        Organization.name.like(kw),
                        OrganizationApplication.reason.like(kw),
                    )
                )
            )

        total = q.count()
        rows = (
            q.order_by(desc(OrganizationApplication.id))
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return OrgApplicationPage(
            total=total,
            page=page,
            page_size=page_size,
            list=[_app_to_out(r) for r in rows],
        )

    # ========== 审核 ==========

    @staticmethod
    def review(
        db: Session,
        *,
        reviewer: User,
        application_id: int,
        params: OrgApplicationReview,
    ) -> OrgApplicationOut:
        """
        管理员审核入口（接受 / 驳回）。
        通过：写 user.department=机构名，向申请人 push 「申请已通过」消息
        驳回：写 review_comment，向申请人 push 「申请已驳回 + 理由」消息
        全过程单事务。
        """
        app = (
            db.query(OrganizationApplication)
            .filter(OrganizationApplication.id == application_id)
            .first()
        )
        if not app:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"申请不存在：{application_id}",
            )
        if app.status != AppStatusEnum.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"申请已审核（{app.status}），无法再次操作",
            )

        comment = (params.comment or "").strip()
        if not params.accept and not comment:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="驳回时必须填写驳回理由",
            )

        org = (
            db.query(Organization)
            .filter(Organization.id == app.organization_id)
            .first()
        )
        org_name = org.name if org else f"机构#{app.organization_id}"

        now = datetime.now()
        if params.accept:
            app.status = AppStatusEnum.APPROVED.value
            app.review_comment = comment
            # 同事务把 User.department 字段写成机构名（不改 schema，仅赋值）
            applicant = (
                db.query(User).filter(User.id == app.applicant_id).first()
            )
            if applicant is not None:
                applicant.department = org_name

            UserMessageService.push(
                db,
                user_id=app.applicant_id,
                msg_type=MessageTypeEnum.ORG_APPLICATION.value,
                title="机构申请已通过",
                content=(
                    f"您申请加入「{org_name}」的请求已通过审核。"
                    + (f"\n审核备注：{comment}" if comment else "")
                ),
                ref_type="org_application",
                ref_id=app.id,
                commit=False,
            )
        else:
            app.status = AppStatusEnum.REJECTED.value
            app.review_comment = comment

            UserMessageService.push(
                db,
                user_id=app.applicant_id,
                msg_type=MessageTypeEnum.ORG_APPLICATION.value,
                title="机构申请未通过",
                content=(
                    f"您申请加入「{org_name}」的请求未通过审核。\n"
                    f"驳回理由：{comment}"
                ),
                ref_type="org_application",
                ref_id=app.id,
                commit=False,
            )

        app.reviewer_id = reviewer.id
        app.reviewed_at = now

        db.commit()
        db.refresh(app)
        return _app_to_out(app)
