"""
CSU-EYES 诊断业务层
==================
- 处理「上传眼底图 + 调 CSU-EYES + 解析结果 + 写回病例」全链路
- 三种入口：
    1) MA 检测（单张）
    2) DR 分级（双眼）
    3) 综合诊断（单张多任务）
- 写入位置：
    - 影像本身 → ScreeningCase.image_paths（OD/OS/OU）
    - 推理结果 → ScreeningResult（每只眼一条；综合 = OU 一条）
    - heatmap / overlay 落盘 → /static/screening/...，URL 写入 ScreeningResult.heatmap_path
- 患者信息：复用 patient_mock 自动生成（仅当用户没填）
- 返回值：DiagnosisOut（含 task_id / 主要展示字段 + 原始上游 JSON）

权限：上层路由用 require_roles(TEACHER, ADMIN) 控制。
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.common.utils import (
    resolve_screening_file,
    save_b64_image_to_screening,
    save_fundus_image,
)
from app.db.models import (
    DrGradeEnum,
    EyeSideEnum,
    GenderEnum,
    RiskLevelEnum,
    RoleEnum,
    ScreeningCase,
    ScreeningResult,
    ScreeningStatusEnum,
    User,
)
from app.schemas.diagnosis import (
    DiagnosisType,
    DrEyeResult,
    DiagnosisOut,
    MaDiagnosisResult,
    DrDiagnosisResult,
    ComprehensiveDiagnosisResult,
)
from app.services import csu_eyes_client


logger = logging.getLogger(__name__)


# ============================================================
#                    工具
# ============================================================

GRADE_TO_RISK = {
    "0": RiskLevelEnum.LOW.value,
    "1": RiskLevelEnum.LOW.value,
    "2": RiskLevelEnum.MEDIUM.value,
    "3": RiskLevelEnum.HIGH.value,
    "4": RiskLevelEnum.URGENT.value,
}


def _next_case_no(db: Session) -> str:
    """生成业务编号 D{YYYYMMDD}-XXXX，按当日记录数自增。"""
    from sqlalchemy import func
    today = datetime.now()
    prefix = f"D{today.strftime('%Y%m%d')}"
    cnt = (
        db.query(func.count(ScreeningCase.id))
        .filter(ScreeningCase.case_no.like(f"{prefix}%"))
        .scalar()
    ) or 0
    return f"{prefix}-{cnt + 1:04d}"


def _grade_str(v) -> str:
    """把 0~4 整数 / 数字字符串规范成 '0'~'4'，其它返回 '0'"""
    try:
        n = int(v)
    except Exception:
        return "0"
    if 0 <= n <= 4:
        return str(n)
    return "0"


def _build_case(
    db: Session,
    *,
    user: User,
    diagnosis_type: DiagnosisType,
    image_paths: dict,
    image_count: int,
    remark: str,
) -> ScreeningCase:
    """新建一个 ScreeningCase，并自动生成模拟患者信息 + case_sn。"""
    from app.services.case_sn import generate_case_sn
    from app.services.patient_mock import generate_mock_patient

    patient = generate_mock_patient(db)

    case = ScreeningCase(
        case_no=_next_case_no(db),
        patient_name=patient.name,
        patient_id_card="",
        gender=patient.gender,
        age=patient.age,
        phone=patient.phone,
        patient_phone=patient.phone,
        chief_complaint=f"CSU-EYES {diagnosis_type.value}",
        medical_history="",
        image_paths=image_paths,
        image_count=image_count,
        status=ScreeningStatusEnum.PROCESSING.value,
        submit_user_id=user.id,
        submit_at=datetime.now(),
        remark=remark or "",
    )
    try:
        case.case_sn = generate_case_sn(db)
    except Exception:
        pass
    db.add(case)
    db.flush()
    return case


# ============================================================
#                    Service
# ============================================================

class DiagnosisService:

    # ----------- 1. MA 检测 -----------
    @staticmethod
    async def ma_detection(
        db: Session,
        user: User,
        file: UploadFile,
        eye: str = "OU",
        model_id: Optional[int] = None,
    ) -> DiagnosisOut:
        """单张眼底图 → MA 检测 → 写入新 ScreeningCase + ScreeningResult。"""
        rel_url, file_name, _ = await save_fundus_image(file, user.id)
        eye_db = (eye or "OU").upper()
        if eye_db not in ("OD", "OS", "OU"):
            eye_db = "OU"

        case = _build_case(
            db, user=user, diagnosis_type=DiagnosisType.MA,
            image_paths={eye_db: [rel_url]}, image_count=1,
            remark="CSU-EYES MA 检测",
        )

        # 调上游
        local_path = resolve_screening_file(rel_url)
        if local_path is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="影像落盘后未能定位本地文件",
            )
        try:
            raw = await csu_eyes_client.detect_ma(image_path=local_path, model_id=model_id)
        except HTTPException:
            case.status = ScreeningStatusEnum.FAILED.value
            db.commit()
            raise
        except Exception as e:
            case.status = ScreeningStatusEnum.FAILED.value
            case.remark = f"CSU-EYES 调用失败：{e}"
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"CSU-EYES 调用失败：{e}",
            )

        ma_count = int(raw.get("ma_count") or 0)
        overlay_url = save_b64_image_to_screening(
            raw.get("overlay_base64") or "",
            prefix="ma_overlay", case_no=case.case_no, suffix=eye_db.lower(),
        )
        heatmap_url = save_b64_image_to_screening(
            raw.get("heatmap_base64") or "",
            prefix="ma_heat", case_no=case.case_no, suffix=eye_db.lower(),
        )

        # 风险等级：按 MA 数量启发（>10=中危，>30=高危，否则正常）
        if ma_count >= 30:
            risk = RiskLevelEnum.HIGH.value
        elif ma_count >= 10:
            risk = RiskLevelEnum.MEDIUM.value
        else:
            risk = RiskLevelEnum.LOW.value

        result = ScreeningResult(
            case_id=case.id,
            eye_side=eye_db,
            model_name="CSU-EYES MA",
            model_version="csu-v1",
            dr_grade=DrGradeEnum.G0.value,
            has_dme=False,
            risk_level=risk,
            risk_score=float(min(0.99, ma_count / 50.0)),
            referral_required=ma_count >= 30,
            lesions=[{"type": "MA", "count": ma_count}],
            annotations=[],
            heatmap_path=overlay_url or heatmap_url or "",
            thumbnail_path=overlay_url or heatmap_url or "",
            infer_duration_ms=int(float(raw.get("inference_time") or 0) * 1000),
            inferred_at=datetime.now(),
        )
        db.add(result)
        case.status = ScreeningStatusEnum.COMPLETED.value
        db.commit()
        db.refresh(case)

        ma_res = MaDiagnosisResult(
            ma_count=ma_count,
            overlay_url=overlay_url,
            heatmap_url=heatmap_url,
            inference_time=float(raw.get("inference_time") or 0),
        )

        return DiagnosisOut(
            task_id=case.case_no,
            case_id=case.id,
            case_sn=case.case_sn or "",
            patient_name=case.patient_name or "",
            diagnosis_type=DiagnosisType.MA,
            risk_level=risk,
            primary_image_url=rel_url,
            ma=ma_res,
            raw=raw,
        )

    # ----------- 2. DR 双眼分级 -----------
    @staticmethod
    async def dr_grading(
        db: Session,
        user: User,
        left_eye: UploadFile,
        right_eye: UploadFile,
        model_id: Optional[int] = None,
    ) -> DiagnosisOut:
        left_url, _, _ = await save_fundus_image(left_eye, user.id)
        right_url, _, _ = await save_fundus_image(right_eye, user.id)

        case = _build_case(
            db, user=user, diagnosis_type=DiagnosisType.DR,
            image_paths={"OS": [left_url], "OD": [right_url]}, image_count=2,
            remark="CSU-EYES DR 分级",
        )

        left_p = resolve_screening_file(left_url)
        right_p = resolve_screening_file(right_url)
        if not left_p or not right_p:
            raise HTTPException(500, detail="DR 分级影像落盘后未能定位本地文件")

        try:
            raw = await csu_eyes_client.grade_dr(
                left_eye_path=left_p, right_eye_path=right_p, model_id=model_id,
            )
        except HTTPException:
            case.status = ScreeningStatusEnum.FAILED.value
            db.commit()
            raise

        left_grade = _grade_str(raw.get("left_eye_prediction"))
        right_grade = _grade_str(raw.get("right_eye_prediction"))
        overall = _grade_str(raw.get("overall_grade"))
        risk = GRADE_TO_RISK.get(overall, RiskLevelEnum.LOW.value)

        left_heatmap = save_b64_image_to_screening(
            raw.get("left_eye_heatmap_base64") or "",
            prefix="dr_heat", case_no=case.case_no, suffix="os",
        )
        right_heatmap = save_b64_image_to_screening(
            raw.get("right_eye_heatmap_base64") or "",
            prefix="dr_heat", case_no=case.case_no, suffix="od",
        )

        # 双眼各写一条 ScreeningResult
        for side, grade, heat in (
            ("OS", left_grade, left_heatmap),
            ("OD", right_grade, right_heatmap),
        ):
            db.add(ScreeningResult(
                case_id=case.id,
                eye_side=side,
                model_name="CSU-EYES DR",
                model_version="csu-v1",
                dr_grade=grade,  # DrGradeEnum 取值是 '0'~'4' 字符串
                has_dme=False,
                risk_level=GRADE_TO_RISK.get(grade, RiskLevelEnum.LOW.value),
                risk_score=float(int(grade) / 4.0),
                referral_required=int(grade) >= 3,
                lesions=[],
                annotations=[],
                heatmap_path=heat or "",
                thumbnail_path=heat or "",
                infer_duration_ms=int(float(raw.get("inference_time") or 0) * 1000),
                inferred_at=datetime.now(),
            ))

        case.status = ScreeningStatusEnum.COMPLETED.value
        db.commit()
        db.refresh(case)

        return DiagnosisOut(
            task_id=case.case_no,
            case_id=case.id,
            case_sn=case.case_sn or "",
            patient_name=case.patient_name or "",
            diagnosis_type=DiagnosisType.DR,
            risk_level=risk,
            primary_image_url=left_url,
            dr=DrDiagnosisResult(
                overall_grade=int(overall),
                overall_grade_name=str(raw.get("overall_grade_name") or ""),
                left=DrEyeResult(
                    grade=int(left_grade),
                    grade_name=str(raw.get("left_eye_grade_name") or ""),
                    image_url=left_url,
                    heatmap_url=left_heatmap,
                ),
                right=DrEyeResult(
                    grade=int(right_grade),
                    grade_name=str(raw.get("right_eye_grade_name") or ""),
                    image_url=right_url,
                    heatmap_url=right_heatmap,
                ),
                inference_time=float(raw.get("inference_time") or 0),
            ),
            raw=raw,
        )

    # ----------- 3. 综合诊断 -----------
    @staticmethod
    async def comprehensive(
        db: Session,
        user: User,
        file: UploadFile,
        tasks: Optional[List[str]] = None,
    ) -> DiagnosisOut:
        rel_url, _, _ = await save_fundus_image(file, user.id)
        case = _build_case(
            db, user=user, diagnosis_type=DiagnosisType.COMPREHENSIVE,
            image_paths={"OU": [rel_url]}, image_count=1,
            remark="CSU-EYES 综合诊断",
        )

        local_path = resolve_screening_file(rel_url)
        if not local_path:
            raise HTTPException(500, detail="综合诊断影像落盘后未能定位本地文件")

        try:
            raw = await csu_eyes_client.comprehensive(image_path=local_path, tasks=tasks)
        except HTTPException:
            case.status = ScreeningStatusEnum.FAILED.value
            db.commit()
            raise

        results = raw.get("results") or {}
        ma_block = results.get("ma_detection") or {}
        dr_block = results.get("dr_grading") or {}

        ma_count = int(ma_block.get("ma_count") or 0)
        ma_overlay = save_b64_image_to_screening(
            ma_block.get("overlay_base64") or "",
            prefix="comp_ma", case_no=case.case_no,
        )

        overall = _grade_str(dr_block.get("overall_grade") or dr_block.get("prediction") or 0)
        risk_from_grade = GRADE_TO_RISK.get(overall, RiskLevelEnum.LOW.value)
        risk_from_ma = (
            RiskLevelEnum.HIGH.value if ma_count >= 30
            else RiskLevelEnum.MEDIUM.value if ma_count >= 10
            else RiskLevelEnum.LOW.value
        )
        # 取风险更高的
        order = {
            RiskLevelEnum.LOW.value: 0,
            RiskLevelEnum.MEDIUM.value: 1,
            RiskLevelEnum.HIGH.value: 2,
            RiskLevelEnum.URGENT.value: 3,
        }
        risk = max([risk_from_grade, risk_from_ma], key=lambda r: order.get(r, 0))

        dr_heat = save_b64_image_to_screening(
            dr_block.get("heatmap_base64") or "",
            prefix="comp_dr", case_no=case.case_no,
        )

        db.add(ScreeningResult(
            case_id=case.id,
            eye_side="OU",
            model_name="CSU-EYES Comprehensive",
            model_version="csu-v1",
            dr_grade=overall,  # '0'~'4'
            has_dme=False,
            risk_level=risk,
            risk_score=float(int(overall) / 4.0),
            referral_required=int(overall) >= 3 or ma_count >= 30,
            lesions=[{"type": "MA", "count": ma_count}] if ma_count else [],
            annotations=[],
            heatmap_path=dr_heat or ma_overlay or "",
            thumbnail_path=ma_overlay or dr_heat or "",
            infer_duration_ms=int(float(raw.get("inference_time") or 0) * 1000),
            inferred_at=datetime.now(),
        ))
        case.status = ScreeningStatusEnum.COMPLETED.value
        db.commit()
        db.refresh(case)

        return DiagnosisOut(
            task_id=case.case_no,
            case_id=case.id,
            case_sn=case.case_sn or "",
            patient_name=case.patient_name or "",
            diagnosis_type=DiagnosisType.COMPREHENSIVE,
            risk_level=risk,
            primary_image_url=rel_url,
            comprehensive=ComprehensiveDiagnosisResult(
                overall_grade=int(overall),
                ma_count=ma_count,
                ma_overlay_url=ma_overlay,
                dr_heatmap_url=dr_heat,
                summary=str(raw.get("summary") or ""),
                inference_time=float(raw.get("inference_time") or 0),
            ),
            raw=raw,
        )


__all__ = ["DiagnosisService"]
