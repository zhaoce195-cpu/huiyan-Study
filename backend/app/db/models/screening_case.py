"""
AI 筛查病例表
- 真实临床患者的眼底影像批次，用于 DR / 青光眼 / AMD 等筛查
- 一份 case 包含 OD（右眼）/ OS（左眼）多张影像，逐一存放在 image_paths（JSON）
"""

from datetime import date, datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class GenderEnum(str, Enum):
    MALE = "M"
    FEMALE = "F"
    UNKNOWN = "U"


class ScreeningStatusEnum(str, Enum):
    PENDING = "PENDING"        # 待筛查
    PROCESSING = "PROCESSING"  # AI 推理中
    COMPLETED = "COMPLETED"    # 已完成
    REVIEWED = "REVIEWED"      # 医生已复核
    FAILED = "FAILED"          # 失败/异常


class ScreeningCase(Base, TimestampMixin):
    __tablename__ = "biz_screening_case"
    __table_args__ = {"comment": "AI 筛查病例表"}

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, comment="筛查病例ID"
    )

    # 业务编号（前端展示用，如 P2026001）
    case_no: Mapped[str] = mapped_column(
        String(32), nullable=False, unique=True, index=True,
        comment="业务编号：P2026001 等",
    )
    case_sn: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, unique=True, index=True,
        comment="全局唯一业务序列号：CASE+YYYYMMDD+6位随机",
    )

    # 患者信息（脱敏存储）
    patient_name: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", comment="患者姓名（可脱敏）"
    )
    patient_id_card: Mapped[str] = mapped_column(
        String(32), nullable=False, default="", index=True,
        comment="身份证号/就诊号（可脱敏）",
    )
    gender: Mapped[str] = mapped_column(
        String(2), nullable=False, default=GenderEnum.UNKNOWN.value,
        comment="性别：M/F/U",
    )
    age: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="年龄"
    )
    birth_date: Mapped[Optional[date]] = mapped_column(
        Date, nullable=True, comment="出生日期"
    )
    phone: Mapped[str] = mapped_column(
        String(20), nullable=False, default="", comment="联系电话"
    )

    patient_phone: Mapped[str] = mapped_column(
        String(20), nullable=False, default="", index=True,
        comment="病患账号手机号（用于病例与 patient 用户绑定）",
    )

    # 临床信息
    chief_complaint: Mapped[str] = mapped_column(
        String(255), nullable=False, default="", comment="主诉"
    )
    medical_history: Mapped[str] = mapped_column(
        Text, nullable=False, default="", comment="病史摘要"
    )
    diabetes_years: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="糖尿病病程（年）"
    )

    # 影像
    image_paths: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True,
        comment="影像路径 JSON：{\"OD\":[\"/static/screening/xxx.jpg\"], \"OS\":[\"...\"]}",
    )
    image_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="影像数量"
    )

    # 状态
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ScreeningStatusEnum.PENDING.value,
        index=True, comment="筛查状态：PENDING/PROCESSING/COMPLETED/REVIEWED/FAILED",
    )

    # ============= 体检报告确认 / 推送 =============
    report_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", index=True,
        comment="报告状态：pending（未确认）/ confirmed（已确认推送）",
    )
    report_pdf_path: Mapped[str] = mapped_column(
        String(512), nullable=False, default="",
        comment="确认后生成的 PDF 报告物理路径（相对 media 根目录）",
    )
    patient_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("sys_user.id", ondelete="SET NULL"),
        nullable=True, index=True,
        comment="确认报告时按手机号绑定的病患用户 ID",
    )

    # 关联
    department_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("biz_department.id", ondelete="SET NULL"),
        nullable=True, index=True, comment="送检科室",
    )
    submit_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sys_user.id", ondelete="RESTRICT"),
        nullable=False, index=True, comment="送检/录入用户ID",
    )
    review_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("sys_user.id", ondelete="SET NULL"),
        nullable=True, comment="复核医生ID",
    )

    submit_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="送检时间"
    )
    review_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="复核时间"
    )

    remark: Mapped[str] = mapped_column(
        String(255), nullable=False, default="", comment="备注"
    )

    # 关系
    submit_user = relationship("User", foreign_keys=[submit_user_id], lazy="joined")
    review_user = relationship("User", foreign_keys=[review_user_id], lazy="joined")
    patient_user = relationship("User", foreign_keys=[patient_user_id], lazy="joined")
    department = relationship("Department", lazy="joined")
    results = relationship(
        "ScreeningResult",
        back_populates="case",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<ScreeningCase {self.case_no} status={self.status}>"
