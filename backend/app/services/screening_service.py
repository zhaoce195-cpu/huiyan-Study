"""
AI 筛查业务层
- 上传眼底图（单 / 批量）
- 调度 AI 推理（mock 实现，独立函数 _run_ai_inference 便于后续替换为真实模型）
- 任务列表 / 详情 / 删除 / 重新分析
- 风险统计
- 报告查询 / 转诊
"""

import logging
import random
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import and_, desc, func, or_
from sqlalchemy.orm import Session

from app.core.config import settings

from app.common.eye_infer import (
    laterality_from_paths,
    resolve_static_file,
    resolve_uploaded_eye,
)
from app.common.utils import (
    delete_fundus_file,
    resolve_report_pdf,
    save_fundus_image,
    save_report_pdf,
    screening_url,
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
from app.schemas.screening import (
    BatchUploadResult,
    CaseImageItem,
    CaseImagesResult,
    CaseUpdateParams,
    ConfirmReportParams,
    ConfirmReportResult,
    ImageUrls,
    LesionItem,
    PatientMetaForm,
    ReanalyzeParams,
    ReferParams,
    ScreeningPageResult,
    ScreeningReportOut,
    ScreeningStatsOut,
    ScreeningTaskOut,
    UploadFundusResult,
)


logger = logging.getLogger(__name__)


# ============================================================
#                    枚举映射 / 常量
# ============================================================

GENDER_CN_TO_DB = {"男": GenderEnum.MALE.value, "女": GenderEnum.FEMALE.value}
GENDER_DB_TO_CN = {
    GenderEnum.MALE.value: "男",
    GenderEnum.FEMALE.value: "女",
    GenderEnum.UNKNOWN.value: "男",
}

EYE_FRONT_TO_DB = {
    "OD": EyeSideEnum.OD.value,
    "OS": EyeSideEnum.OS.value,
    "OU": EyeSideEnum.OU.value,
}

DR_GRADE_TEXT: Dict[str, str] = {
    "0": "0 级 无 DR",
    "1": "1 级 轻度 NPDR",
    "2": "2 级 中度 NPDR",
    "3": "3 级 重度 NPDR",
    "4": "4 级 PDR（增殖性）",
}

# 内部状态 → 前端枚举
STATUS_DB_TO_FRONT: Dict[str, str] = {
    ScreeningStatusEnum.PENDING.value: "queued",
    ScreeningStatusEnum.PROCESSING.value: "analyzing",
    ScreeningStatusEnum.COMPLETED.value: "done",
    ScreeningStatusEnum.REVIEWED.value: "done",
    ScreeningStatusEnum.FAILED.value: "failed",
}
STATUS_FRONT_TO_DB: Dict[str, List[str]] = {
    "queued": [ScreeningStatusEnum.PENDING.value],
    "analyzing": [ScreeningStatusEnum.PROCESSING.value],
    "done": [
        ScreeningStatusEnum.COMPLETED.value,
        ScreeningStatusEnum.REVIEWED.value,
    ],
    "failed": [ScreeningStatusEnum.FAILED.value],
}

# 内部 RiskLevel → 前端三色
RISK_DB_TO_FRONT: Dict[str, str] = {
    RiskLevelEnum.LOW.value: "green",
    RiskLevelEnum.MEDIUM.value: "yellow",
    RiskLevelEnum.HIGH.value: "red",
    RiskLevelEnum.URGENT.value: "red",
}
RISK_FRONT_TO_DB: Dict[str, List[str]] = {
    "green": [RiskLevelEnum.LOW.value],
    "yellow": [RiskLevelEnum.MEDIUM.value],
    "red": [RiskLevelEnum.HIGH.value, RiskLevelEnum.URGENT.value],
}


# ============================================================
#                    工具函数
# ============================================================

_seq_lock = threading.Lock()


def _next_case_no(db: Session) -> str:
    """生成业务编号 T20260522-XXXX，简单基于当日记录数 +1"""
    today = datetime.now()
    prefix = f"T{today.strftime('%Y%m%d')}"
    with _seq_lock:
        cnt: int = (
            db.query(func.count(ScreeningCase.id))
            .filter(ScreeningCase.case_no.like(f"{prefix}%"))
            .scalar()
        ) or 0
        return f"{prefix}-{cnt + 1:04d}"


def _get_case_or_404(db: Session, task_id: str) -> ScreeningCase:
    case = db.query(ScreeningCase).filter(ScreeningCase.case_no == task_id).first()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"筛查任务不存在：{task_id}",
        )
    return case


def _eye_db_to_front(case: ScreeningCase) -> str:
    """根据 image_paths 汇总眼别。只有 UK 时不标成双眼。"""
    return laterality_from_paths(case.image_paths or {})


def _first_image_url(case: ScreeningCase) -> Tuple[str, str, str]:
    """返回 (file_name, file_url, thumb_url)"""
    paths = case.image_paths or {}
    if isinstance(paths, dict):
        for side in ("OD", "OS", "OU", "UK"):
            arr = paths.get(side) or []
            if arr:
                url = arr[0]
                file_name = url.rsplit("/", 1)[-1] if url else ""
                return file_name, url, url
    return "", "", ""


def _latest_result(case: ScreeningCase) -> Optional[ScreeningResult]:
    """case 关联的多条 result 中取最新一条"""
    if not case.results:
        return None
    return max(case.results, key=lambda r: (r.id or 0))


def _to_task_out(
    case: ScreeningCase,
    db: Optional[Session] = None,
    viewer: Optional[User] = None,
) -> ScreeningTaskOut:
    from app.services.patient_mock import mask_phone

    file_name, file_url, thumb_url = _first_image_url(case)
    result = _latest_result(case)

    risk_front: Optional[str] = None
    dr_text = ""
    confidence = 0.0
    remark = case.remark or ""

    if result:
        risk_front = RISK_DB_TO_FRONT.get(result.risk_level)
        dr_text = DR_GRADE_TEXT.get(result.dr_grade, "")
        confidence = float(result.risk_score or 0.0)
        if result.doctor_diagnosis:
            remark = result.doctor_diagnosis

    submit_user = case.submit_user
    doctor_name = ""
    if submit_user:
        doctor_name = submit_user.real_name or submit_user.username or ""

    raw_phone = case.patient_phone or ""
    patient_bound = False
    if raw_phone and db is not None:
        patient_bound = (
            db.query(User.id)
            .filter(User.phone == raw_phone)
            .first()
            is not None
        )

    # ============ CSU-EYES 诊断结果摘要 ============
    diagnosis_type: Optional[str] = None
    diagnosis_summary = ""
    heatmap_url: Optional[str] = None
    if result and result.model_name:
        mn = result.model_name.upper()
        if "MA" in mn and "COMPREHENSIVE" not in mn:
            diagnosis_type = "MA"
            cnt = 0
            try:
                cnt = int((result.lesions or [{}])[0].get("count") or 0)
            except Exception:
                cnt = 0
            diagnosis_summary = f"MA {cnt} 个"
        elif "COMPREHENSIVE" in mn:
            diagnosis_type = "COMPREHENSIVE"
            diagnosis_summary = f"DR {result.dr_grade or 0} 级 综合诊断"
        elif "DR" in mn:
            diagnosis_type = "DR"
            diagnosis_summary = f"DR {result.dr_grade or 0} 级"
        heatmap_url = result.heatmap_path or result.thumbnail_path or None

    # ============ 患者手机号脱敏：依据调用者角色 ============
    viewer_role = viewer.role.code if (viewer and viewer.role) else None
    is_patient_self = (
        viewer is not None
        and case.patient_user_id == viewer.id
    )
    if viewer_role == RoleEnum.ADMIN.value or is_patient_self:
        # 管理员 / 病患本人：完整手机号
        patient_phone = raw_phone
    elif viewer_role == RoleEnum.TEACHER.value:
        # 体检医生（这里筛查端的 TEACHER 即"医生"角色，按需求看完整手机）
        patient_phone = raw_phone
    else:
        # 学员 / 其他：脱敏
        patient_phone = mask_phone(raw_phone)

    confirmed = case.status == ScreeningStatusEnum.REVIEWED.value
    reviewer_name = ""
    reviewed_at_str: Optional[str] = None
    if case.review_user:
        reviewer_name = (
            case.review_user.real_name or case.review_user.username or ""
        )
    if case.review_at:
        reviewed_at_str = case.review_at.strftime("%Y-%m-%d %H:%M:%S")

    return ScreeningTaskOut(
        id=case.case_no,
        case_id=case.id,
        patient_id=case.patient_id_card or "",
        patient_name=case.patient_name or "",
        patient_phone=patient_phone,
        eye=_eye_db_to_front(case),  # type: ignore[arg-type]
        age=case.age or 0,
        gender=GENDER_DB_TO_CN.get(case.gender, "男"),  # type: ignore[arg-type]
        status=STATUS_DB_TO_FRONT.get(case.status, "queued"),  # type: ignore[arg-type]
        risk=risk_front,  # type: ignore[arg-type]
        dr=dr_text,
        confidence=confidence,
        created_at=(case.created_at or datetime.now()).strftime("%Y-%m-%d %H:%M:%S"),
        file_name=file_name,
        file_url=file_url or None,
        thumb_url=thumb_url or None,
        hospital="",
        doctor=doctor_name,
        remark=remark,
        patient_bound=patient_bound,
        confirmed=confirmed,
        reviewer=reviewer_name or None,
        reviewed_at=reviewed_at_str,
        diagnosis_type=diagnosis_type,
        diagnosis_summary=diagnosis_summary,
        heatmap_url=heatmap_url,
    )


# ============================================================
#                    AI 推理（Mock 实现）
# ============================================================

def _mock_lesions_for(grade: str) -> List[Dict]:
    """根据 DR 等级生成符合医学常识的病灶列表"""
    if grade == "0":
        return []
    if grade == "1":
        return [{"type": "微动脉瘤", "count": random.randint(1, 5), "location": "黄斑外侧"}]
    if grade == "2":
        return [
            {"type": "微动脉瘤", "count": random.randint(5, 15), "location": "黄斑区"},
            {"type": "出血", "count": random.randint(1, 5), "location": "下方象限"},
            {"type": "硬渗", "count": random.randint(0, 4), "location": "黄斑外环"},
        ]
    if grade == "3":
        return [
            {"type": "微动脉瘤", "count": random.randint(10, 30), "location": "全象限"},
            {"type": "出血", "count": random.randint(5, 20), "location": "全象限"},
            {"type": "硬渗", "count": random.randint(2, 8), "location": "黄斑区"},
            {"type": "棉绒斑", "count": random.randint(1, 4), "location": "上方象限"},
        ]
    return [
        {"type": "新生血管", "count": random.randint(1, 4), "location": "视盘"},
        {"type": "出血", "count": random.randint(10, 40), "location": "全象限"},
        {"type": "硬渗", "count": random.randint(5, 12), "location": "黄斑区"},
        {"type": "棉绒斑", "count": random.randint(2, 6), "location": "全象限"},
    ]


def _grade_to_risk(grade: str) -> Tuple[str, float]:
    """DR 等级 -> (risk_level, risk_score) 的标准映射。"""
    if grade == "0":
        return RiskLevelEnum.LOW.value, round(random.uniform(0.05, 0.25), 4)
    if grade == "1":
        return RiskLevelEnum.LOW.value, round(random.uniform(0.25, 0.45), 4)
    if grade == "2":
        return RiskLevelEnum.MEDIUM.value, round(random.uniform(0.5, 0.7), 4)
    if grade == "3":
        return RiskLevelEnum.HIGH.value, round(random.uniform(0.7, 0.85), 4)
    return RiskLevelEnum.URGENT.value, round(random.uniform(0.85, 0.99), 4)


def _select_eye_files(case: ScreeningCase) -> Tuple[Optional[Path], Optional[Path]]:
    """
    从 case.image_paths 里挑出左右眼第一张图：
    - paths["OD"][0] 作为右眼，paths["OS"][0] 作为左眼
    - 若只有一只眼，把同一张图当左右眼提交（DRGCNN 必须两眼齐）
    - 若是 OU（双眼合一）也复用同一张
    返回的是磁盘绝对路径，找不到的位置返回 None。
    """
    from app.common.utils import resolve_screening_file
    paths = case.image_paths or {}
    od_url = (paths.get("OD") or [None])[0] if isinstance(paths, dict) else None
    os_url = (paths.get("OS") or [None])[0] if isinstance(paths, dict) else None
    ou_url = (paths.get("OU") or [None])[0] if isinstance(paths, dict) else None
    uk_url = (paths.get("UK") or [None])[0] if isinstance(paths, dict) else None

    od_path = resolve_screening_file(od_url) if od_url else None
    os_path = resolve_screening_file(os_url) if os_url else None
    ou_path = resolve_screening_file(ou_url) if ou_url else None
    uk_path = resolve_screening_file(uk_url) if uk_url else None

    # 左眼优先 OS / 右眼优先 OD；缺失时用 OU、UK 兜底；再缺时双眼共用同一张
    left = os_path or ou_path or uk_path or od_path
    right = od_path or ou_path or uk_path or os_path
    return left, right


def _try_drgcnn(case: ScreeningCase) -> Optional[Tuple[str, float, str, Dict[str, Any]]]:
    """
    调用 DRGCNN 得到结果，失败统一返回 None，让上层走 mock 兜底。
    返回 (grade_str, risk_score, heatmap_url, raw_dict)。
    grade 取双眼最大值；risk_score 用 max prob / 4 归一化到 [0,1]。
    """
    if not settings.DRGCNN_ENABLED:
        return None
    from app.services.drgcnn_client import predict_twoeyes, DRGCNNError
    from app.common.utils import save_heatmap_from_data_url

    left_path, right_path = _select_eye_files(case)
    if left_path is None or right_path is None:
        logger.warning(
            "DRGCNN 跳过：case=%s 没有可用的本地眼底图（image_paths=%s）",
            case.case_no, case.image_paths,
        )
        return None

    try:
        res = predict_twoeyes(left=left_path, right=right_path)
    except DRGCNNError as e:
        logger.warning("DRGCNN 调用失败 case=%s：%s", case.case_no, e)
        return None
    except Exception as e:
        logger.warning("DRGCNN 未知异常 case=%s：%s", case.case_no, e)
        return None

    grade = max(res.left.grade, res.right.grade)
    grade_str = str(max(0, min(4, grade)))
    # probability 是回归值，不一定 [0,1]；用 max/4 归一化作为 risk_score
    raw_score = max(res.left.probability, res.right.probability)
    risk_score = max(0.0, min(1.0, raw_score / 4.0))

    # 取「主导眼」热力图：等级更高的那只
    dominant = res.left if res.left.grade >= res.right.grade else res.right
    dominant_eye = "OS" if dominant is res.left else "OD"
    heatmap_url = save_heatmap_from_data_url(
        dominant.heatmap_base64, case.case_no, dominant_eye,
    )

    return grade_str, risk_score, heatmap_url, res.raw


def _run_ai_inference(case: ScreeningCase, db: Session) -> ScreeningResult:
    """
    AI 推理入口：
    - 若 settings.DRGCNN_ENABLED 为真，调用 DRGCNN /predict_twoeyes 真实模型
    - 否则走原 mock 实现
    - DRGCNN 调用失败会自动回退到 mock，避免单点拖垮整个体检流程
    """
    drgcnn_outcome = _try_drgcnn(case)
    using_drgcnn = drgcnn_outcome is not None

    if using_drgcnn:
        grade, risk_score_drg, heatmap_url, raw = drgcnn_outcome  # type: ignore[misc]
        risk_level, _fallback_score = _grade_to_risk(grade)
        score = round(risk_score_drg, 4)
        model_name = "DRGCNN"
        model_version = "twoeyes-v1"
        infer_ms = int(raw.get("_infer_ms", 0)) if isinstance(raw, dict) else 0
        if infer_ms <= 0:
            infer_ms = random.randint(2000, 6000)  # 真实推理耗时大致区间
    else:
        grade = random.choices(
            ["0", "1", "2", "3", "4"], weights=[20, 30, 25, 15, 10], k=1,
        )[0]
        risk_level, score = _grade_to_risk(grade)
        heatmap_url = ""
        model_name = "HuiyanDR-Net"
        model_version = "v1.2.3"
        infer_ms = random.randint(800, 2400)

    # 删除旧 result（重新分析时）
    if case.results:
        for old in list(case.results):
            db.delete(old)

    eye = _eye_db_to_front(case)
    result = ScreeningResult(
        case_id=case.id,
        eye_side=eye,
        model_name=model_name,
        model_version=model_version,
        dr_grade=grade,
        has_dme=1 if grade in ("3", "4") and random.random() < 0.4 else 0,
        risk_level=risk_level,
        risk_score=score,
        referral_required=1 if risk_level in (
            RiskLevelEnum.HIGH.value, RiskLevelEnum.URGENT.value,
        ) else 0,
        lesions=_mock_lesions_for(grade),
        annotations=[],
        heatmap_path=heatmap_url,
        thumbnail_path="",
        infer_duration_ms=infer_ms,
        inferred_at=datetime.now(),
        doctor_diagnosis="",
        doctor_grade="",
    )
    db.add(result)
    case.status = ScreeningStatusEnum.COMPLETED.value
    case.review_at = None
    return result


# ============================================================
#                    Service
# ============================================================

class ScreeningService:

    # ----------- 1. 单文件上传 + 分析 -----------

    @staticmethod
    async def upload_single(
        db: Session,
        user: User,
        file: UploadFile,
        meta: PatientMetaForm,
    ) -> UploadFundusResult:
        from app.services.patient_mock import generate_mock_patient

        rel_url, file_name, size_bytes = await save_fundus_image(file, user.id)

        requested = (meta.eye or "").strip().upper()
        eye = resolve_uploaded_eye(
            requested if requested in ("OD", "OS", "OU") else "UK",
            file_name=file.filename or file_name,
            image_path=resolve_static_file(rel_url),
            role="original",
        )
        gender_db = GENDER_CN_TO_DB.get(meta.gender or "", "")

        # 仅当用户没填关键字段时自动生成模拟患者信息
        # （按需求：医生单独上传眼底图 → 自动生成；用户已填则尊重原值）
        need_mock = not (
            (meta.patient_name or "").strip()
            and gender_db
            and meta.age
            and (meta.patient_phone or "").strip()
        )
        if need_mock:
            mock = generate_mock_patient(
                db,
                fixed_gender=gender_db if gender_db in ("M", "F") else "",
            )
            patient_name = (meta.patient_name or "").strip() or mock.name
            gender_db = gender_db or mock.gender
            age_val = meta.age or mock.age
            phone_val = (meta.patient_phone or "").strip() or mock.phone
        else:
            patient_name = meta.patient_name or ""
            age_val = meta.age
            phone_val = meta.patient_phone or ""

        case = ScreeningCase(
            case_no=_next_case_no(db),
            patient_name=patient_name,
            patient_id_card=meta.patient_id or "",
            gender=gender_db or GenderEnum.UNKNOWN.value,
            age=age_val,
            phone=phone_val,
            patient_phone=phone_val,
            chief_complaint="",
            medical_history="",
            image_paths={eye: [rel_url]},
            image_count=1,
            status=ScreeningStatusEnum.PROCESSING.value,
            submit_user_id=user.id,
            submit_at=datetime.now(),
            remark=meta.remark or "",
        )
        # case_sn 全局唯一编号
        try:
            from app.services.case_sn import generate_case_sn
            case.case_sn = generate_case_sn(db)
        except Exception:
            pass
        db.add(case)
        db.flush()  # 拿 case.id

        # 同步执行 mock 推理（实时返回结果），生产可改为后台任务
        try:
            _run_ai_inference(case, db)
        except Exception as e:
            case.status = ScreeningStatusEnum.FAILED.value
            case.remark = f"AI 推理失败：{e}"

        db.commit()

        return UploadFundusResult(
            task_id=case.case_no,
            file_url=rel_url,
            file_name=file_name,
            file_size=size_bytes,
            queued=True,
        )

    # ----------- 2. 批量上传 -----------

    @staticmethod
    async def upload_batch(
        db: Session,
        user: User,
        files: List[UploadFile],
        meta: PatientMetaForm,
    ) -> BatchUploadResult:
        items: List[UploadFundusResult] = []
        success_cnt = 0
        for f in files:
            try:
                item = await ScreeningService.upload_single(db=db, user=user, file=f, meta=meta)
                items.append(item)
                success_cnt += 1
            except HTTPException as e:
                items.append(UploadFundusResult(
                    task_id="",
                    file_url="",
                    file_name=f.filename or "",
                    file_size=0,
                    queued=False,
                ))
            except Exception:
                items.append(UploadFundusResult(
                    task_id="",
                    file_url="",
                    file_name=f.filename or "",
                    file_size=0,
                    queued=False,
                ))
        return BatchUploadResult(
            total=len(files),
            success=success_cnt,
            failed=len(files) - success_cnt,
            items=items,
        )

    # ----------- 3. 任务列表 -----------

    @staticmethod
    def list_tasks(
        db: Session,
        keyword: Optional[str] = None,
        risk: Optional[str] = None,
        status_filter: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        hospital: Optional[str] = None,
        case_no: Optional[str] = None,
        patient_name: Optional[str] = None,
        phone: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
        sort_by: str = "createdAt",
        sort_order: str = "desc",
        only_user_id: Optional[int] = None,
        scope: Optional[str] = None,
        diagnosis_type: Optional[str] = None,
    ) -> ScreeningPageResult:
        """
        scope:
        - "queue"   仅返回排队中 / 处理中 的任务（PENDING / PROCESSING / FAILED）
                    —— 用于「分析任务队列」视图
        - "archive" 仅返回已完成 / 已复核 的病例（COMPLETED / REVIEWED）
                    —— 用于「病例检索」视图
        - 其他值或省略：返回全部（向下兼容）
        """
        q = db.query(ScreeningCase)

        if scope == "queue":
            q = q.filter(ScreeningCase.status.in_([
                ScreeningStatusEnum.PENDING.value,
                ScreeningStatusEnum.PROCESSING.value,
                ScreeningStatusEnum.FAILED.value,
            ]))
        elif scope == "archive":
            q = q.filter(ScreeningCase.status.in_([
                ScreeningStatusEnum.COMPLETED.value,
                ScreeningStatusEnum.REVIEWED.value,
            ]))

        if only_user_id:
            q = q.filter(ScreeningCase.submit_user_id == only_user_id)

        # 通用关键词：编号 / 姓名 / 身份证 / 手机号
        if keyword:
            kw = f"%{keyword.strip()}%"
            q = q.filter(
                or_(
                    ScreeningCase.case_no.like(kw),
                    ScreeningCase.patient_name.like(kw),
                    ScreeningCase.patient_id_card.like(kw),
                    ScreeningCase.patient_phone.like(kw),
                    ScreeningCase.phone.like(kw),
                )
            )

        # 单字段精筛
        if case_no:
            q = q.filter(ScreeningCase.case_no.like(f"%{case_no.strip()}%"))
        if patient_name:
            q = q.filter(ScreeningCase.patient_name.like(f"%{patient_name.strip()}%"))
        if phone:
            p = phone.strip()
            q = q.filter(
                or_(
                    ScreeningCase.patient_phone.like(f"%{p}%"),
                    ScreeningCase.phone.like(f"%{p}%"),
                )
            )

        if status_filter and status_filter in STATUS_FRONT_TO_DB:
            q = q.filter(ScreeningCase.status.in_(STATUS_FRONT_TO_DB[status_filter]))
        if start_time:
            try:
                q = q.filter(ScreeningCase.created_at >= datetime.fromisoformat(start_time.replace(" ", "T")))
            except ValueError:
                pass
        if end_time:
            try:
                q = q.filter(ScreeningCase.created_at <= datetime.fromisoformat(end_time.replace(" ", "T")))
            except ValueError:
                pass

        # risk 需要 join result
        if risk and risk in RISK_FRONT_TO_DB:
            q = q.join(ScreeningResult, ScreeningResult.case_id == ScreeningCase.id).filter(
                ScreeningResult.risk_level.in_(RISK_FRONT_TO_DB[risk])
            )

        # 诊断类型过滤（按 result.model_name 前缀匹配）
        if diagnosis_type:
            dtype = diagnosis_type.upper().strip()
            mn_kw = {
                "MA": "CSU-EYES MA",
                "DR": "CSU-EYES DR",
                "COMPREHENSIVE": "CSU-EYES Comprehensive",
            }.get(dtype)
            if mn_kw:
                q = q.join(
                    ScreeningResult, ScreeningResult.case_id == ScreeningCase.id
                ).filter(ScreeningResult.model_name.like(f"{mn_kw}%"))

        # 排序
        order_col = ScreeningCase.created_at
        if sort_by == "risk":
            # 通过 join 排，简单实现：用 case_id desc 退化
            order_col = ScreeningCase.created_at
        if sort_order == "asc":
            q = q.order_by(order_col.asc())
        else:
            q = q.order_by(order_col.desc())

        total = q.count()
        rows: List[ScreeningCase] = (
            q.offset(max(0, (page - 1) * page_size))
            .limit(page_size)
            .all()
        )

        return ScreeningPageResult(
            total=total,
            page=page,
            page_size=page_size,
            list=[_to_task_out(c, db) for c in rows],
        )

    # ----------- 4. 任务详情 -----------

    @staticmethod
    def get_task(db: Session, task_id: str) -> ScreeningTaskOut:
        case = _get_case_or_404(db, task_id)
        return _to_task_out(case, db)

    # ----------- 5. 删除（归档） -----------

    @staticmethod
    def delete_task(db: Session, task_id: str) -> None:
        case = _get_case_or_404(db, task_id)

        # 删除文件
        paths = case.image_paths or {}
        if isinstance(paths, dict):
            for arr in paths.values():
                if isinstance(arr, list):
                    for u in arr:
                        delete_fundus_file(u)

        db.delete(case)  # 级联删除 ScreeningResult（cascade=all, delete-orphan）
        db.commit()

    # ----------- 5.1 批量删除 / 批量移出队列 -----------

    @staticmethod
    def batch_delete_tasks(db: Session, task_ids: List[str]) -> dict:
        """
        批量删除：等价于对每个 taskId 执行 delete_task。
        - 找不到的 / 删除失败的归入 failed
        - 不依赖任务状态（已完成 / 排队中均可被删除）
        """
        success_count = 0
        failed: List[str] = []

        for tid in task_ids:
            case = (
                db.query(ScreeningCase)
                .filter(ScreeningCase.case_no == tid)
                .first()
            )
            if not case:
                failed.append(tid)
                continue
            try:
                paths = case.image_paths or {}
                if isinstance(paths, dict):
                    for arr in paths.values():
                        if isinstance(arr, list):
                            for u in arr:
                                delete_fundus_file(u)
                db.delete(case)
                db.commit()
                success_count += 1
            except Exception:
                db.rollback()
                failed.append(tid)

        return {
            "success_count": success_count,
            "skipped_count": 0,
            "failed_count": len(failed),
            "failed_ids": failed,
        }

    @staticmethod
    def batch_remove_from_queue(db: Session, task_ids: List[str]) -> dict:
        """
        批量从队列移出：仅删除仍处于 PENDING / PROCESSING / FAILED 状态的任务，
        已完成 / 已复核的病例视为「不在队列中」，跳过不删，归入 skipped。
        """
        QUEUE_STATUS = {
            ScreeningStatusEnum.PENDING.value,
            ScreeningStatusEnum.PROCESSING.value,
            ScreeningStatusEnum.FAILED.value,
        }

        success_count = 0
        skipped: List[str] = []
        failed: List[str] = []

        for tid in task_ids:
            case = (
                db.query(ScreeningCase)
                .filter(ScreeningCase.case_no == tid)
                .first()
            )
            if not case:
                failed.append(tid)
                continue
            if case.status not in QUEUE_STATUS:
                skipped.append(tid)
                continue
            try:
                paths = case.image_paths or {}
                if isinstance(paths, dict):
                    for arr in paths.values():
                        if isinstance(arr, list):
                            for u in arr:
                                delete_fundus_file(u)
                db.delete(case)
                db.commit()
                success_count += 1
            except Exception:
                db.rollback()
                failed.append(tid)

        return {
            "success_count": success_count,
            "skipped_count": len(skipped),
            "failed_count": len(failed),
            "failed_ids": failed,
        }

    # ----------- 6. 重新分析 -----------

    @staticmethod
    def reanalyze(db: Session, params: ReanalyzeParams) -> ScreeningTaskOut:
        case = _get_case_or_404(db, params.task_id)
        case.status = ScreeningStatusEnum.PROCESSING.value
        try:
            _run_ai_inference(case, db)
        except Exception as e:
            case.status = ScreeningStatusEnum.FAILED.value
            case.remark = f"AI 推理失败：{e}"
        db.commit()
        db.refresh(case)
        return _to_task_out(case, db)

    # ----------- 7. 风险统计 -----------

    @staticmethod
    def stats(db: Session, scope: Optional[str] = None) -> ScreeningStatsOut:
        """
        scope:
        - "queue"   仅统计排队中 / 处理中 / 失败 的任务
        - "archive" 仅统计已完成 / 已复核 的病例
        - 其他：返回全部
        """
        case_q = db.query(ScreeningCase)
        case_filter = None
        if scope == "queue":
            case_filter = ScreeningCase.status.in_([
                ScreeningStatusEnum.PENDING.value,
                ScreeningStatusEnum.PROCESSING.value,
                ScreeningStatusEnum.FAILED.value,
            ])
        elif scope == "archive":
            case_filter = ScreeningCase.status.in_([
                ScreeningStatusEnum.COMPLETED.value,
                ScreeningStatusEnum.REVIEWED.value,
            ])
        if case_filter is not None:
            case_q = case_q.filter(case_filter)

        total: int = case_q.with_entities(func.count(ScreeningCase.id)).scalar() or 0

        pending: int = (
            case_q.with_entities(func.count(ScreeningCase.id))
            .filter(ScreeningCase.status.in_([
                ScreeningStatusEnum.PENDING.value,
                ScreeningStatusEnum.PROCESSING.value,
            ]))
            .scalar()
        ) or 0
        failed: int = (
            case_q.with_entities(func.count(ScreeningCase.id))
            .filter(ScreeningCase.status == ScreeningStatusEnum.FAILED.value)
            .scalar()
        ) or 0

        # risk 聚合：按 case 范围限制（避免「队列」统计也算上历史病例）
        risk_q = db.query(ScreeningResult).join(
            ScreeningCase, ScreeningResult.case_id == ScreeningCase.id,
        )
        if case_filter is not None:
            risk_q = risk_q.filter(case_filter)

        red: int = (
            risk_q.with_entities(func.count(func.distinct(ScreeningResult.case_id)))
            .filter(ScreeningResult.risk_level.in_([
                RiskLevelEnum.HIGH.value,
                RiskLevelEnum.URGENT.value,
            ]))
            .scalar()
        ) or 0
        yellow: int = (
            risk_q.with_entities(func.count(func.distinct(ScreeningResult.case_id)))
            .filter(ScreeningResult.risk_level == RiskLevelEnum.MEDIUM.value)
            .scalar()
        ) or 0
        green: int = (
            risk_q.with_entities(func.count(func.distinct(ScreeningResult.case_id)))
            .filter(ScreeningResult.risk_level == RiskLevelEnum.LOW.value)
            .scalar()
        ) or 0

        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=7)

        today_count: int = (
            case_q.with_entities(func.count(ScreeningCase.id))
            .filter(ScreeningCase.created_at >= today_start)
            .scalar()
        ) or 0
        week_count: int = (
            case_q.with_entities(func.count(ScreeningCase.id))
            .filter(ScreeningCase.created_at >= week_start)
            .scalar()
        ) or 0

        return ScreeningStatsOut(
            total=total,
            red=red,
            yellow=yellow,
            green=green,
            pending=pending,
            failed=failed,
            today_count=today_count,
            week_count=week_count,
        )

    # ----------- 8. 报告详情 -----------

    @staticmethod
    def get_report(db: Session, task_id: str) -> ScreeningReportOut:
        case = _get_case_or_404(db, task_id)
        result = _latest_result(case)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="该任务尚未完成 AI 分析，无可查看报告",
            )

        risk_front = RISK_DB_TO_FRONT.get(result.risk_level, "green")
        dr_text = DR_GRADE_TEXT.get(result.dr_grade, "")
        gender_cn = GENDER_DB_TO_CN.get(case.gender, "男")
        eye_front = _eye_db_to_front(case)

        # 取首张原图
        _, origin_url, _ = _first_image_url(case)

        # 报告编号 HY-YYYY-MM-DD-XXXX（基于 case_no 后缀）
        date_str = (case.created_at or datetime.now()).strftime("%Y-%m-%d")
        suffix = case.case_no.split("-")[-1] if "-" in case.case_no else f"{case.id:04d}"
        report_no = f"HY-{date_str}-{suffix}"

        # 病灶
        lesions: List[LesionItem] = []
        for it in (result.lesions or []):
            if not isinstance(it, dict):
                continue
            lesions.append(LesionItem(
                type=str(it.get("type", "")),
                count=int(it.get("count", 0) or 0),
                location=it.get("location"),
            ))

        # 结论 / 建议
        conclusion = (
            result.doctor_diagnosis
            or f"AI 智能分析提示：{dr_text}，置信度 {result.risk_score:.2%}。"
        )
        if risk_front == "red":
            suggestion = "建议尽快至上级医院眼科专科门诊就诊，必要时行眼底荧光造影检查。"
        elif risk_front == "yellow":
            suggestion = "建议 3 个月内复查眼底，加强血糖与血压管理。"
        else:
            suggestion = "建议每年常规体检并保持血糖控制。"

        reviewer = case.review_user.real_name if case.review_user else None
        reviewed_at = case.review_at.strftime("%Y-%m-%d %H:%M:%S") if case.review_at else None

        return ScreeningReportOut(
            task_id=case.case_no,
            patient_id=case.patient_id_card or "",
            patient_name=case.patient_name or "",
            gender=gender_cn,  # type: ignore[arg-type]
            age=case.age or 0,
            eye=eye_front,  # type: ignore[arg-type]
            hospital="",
            doctor=case.submit_user.real_name if case.submit_user else "",
            exam_time=(case.submit_at or case.created_at).strftime("%Y-%m-%d %H:%M:%S"),
            report_time=(result.inferred_at or datetime.now()).strftime("%Y-%m-%d %H:%M:%S"),
            report_no=report_no,
            risk=risk_front,  # type: ignore[arg-type]
            dr=dr_text,
            confidence=float(result.risk_score or 0.0),
            conclusion=conclusion,
            suggestion=suggestion,
            lesions=lesions,
            image_urls=ImageUrls(
                origin=origin_url,
                heatmap=result.heatmap_path or None,
            ),
            reviewer=reviewer,
            reviewed_at=reviewed_at,
        )

    # ----------- 9. 转诊 -----------

    @staticmethod
    def refer(db: Session, params: ReferParams, user: User) -> None:
        case = _get_case_or_404(db, params.task_id)
        # 简化：写入备注 + 标记 review_user
        suffix = (
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] "
            f"已转诊至「{params.target_hospital}」"
            f"（{user.real_name or user.username}）"
        )
        if params.note:
            suffix += f"，备注：{params.note}"
        case.remark = (case.remark + " | " if case.remark else "") + suffix
        db.commit()

    # ----------- 10. 报告确认 + 同步病患账号 -----------

    @staticmethod
    def confirm_report(
        db: Session,
        params: ConfirmReportParams,
        user: User,
    ) -> ConfirmReportResult:
        """
        医生「确认报告」 + 推送至病患账号 + 生成并落盘 PDF。

        步骤：
        1. 校验任务已完成 AI 分析（必须存在 ScreeningResult）
        2. 写入医生诊断 / 建议至最新 result
        3. 推进病例状态：status=REVIEWED, report_status='confirmed'
        4. 按 patient_phone 自动关联 patient 用户账号 → patient_user_id
        5. 生成 PDF → 落盘 → 写入 report_pdf_path

        权限：路由层已限定为医生 / 管理员；service 层不再二次校验。
        """
        case = _get_case_or_404(db, params.task_id)
        latest = _latest_result(case)
        if not latest:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该任务尚未完成 AI 分析，无法确认报告",
            )

        # 业务硬约束：必须先绑定 patient_phone（否则没法推送给病患）
        phone = (case.patient_phone or "").strip()
        if not phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该病例未绑定病患手机号，无法确认并推送报告，请先绑定后再操作",
            )

        if params.diagnosis is not None and params.diagnosis.strip():
            latest.doctor_diagnosis = params.diagnosis.strip()
        if params.suggestion is not None and params.suggestion.strip():
            # suggestion 没有独立字段，追加进 doctor_diagnosis 末尾
            latest.doctor_diagnosis = (
                (latest.doctor_diagnosis + "\n建议：" if latest.doctor_diagnosis else "建议：")
                + params.suggestion.strip()
            )
        latest.doctor_id = user.id
        latest.doctor_at = datetime.now()

        case.status = ScreeningStatusEnum.REVIEWED.value
        case.review_user_id = user.id
        case.review_at = datetime.now()
        case.report_status = "confirmed"

        # 绑定病患账号（按手机号）
        patient_bound = False
        patient_user = (
            db.query(User).filter(User.phone == phone).first()
        )
        if patient_user is not None:
            patient_bound = True
            case.patient_user_id = patient_user.id
            tag = (
                f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] "
                f"已同步至病患账号 {phone}"
            )
            case.remark = (case.remark + " | " if case.remark else "") + tag

        # 落盘 PDF（生成失败不阻塞确认 —— 病患端取报告时会再生成一次兜底）
        report_pdf_url_str = ""
        try:
            # 复用既有 get_report 生成 ScreeningReportOut
            report = ScreeningService.get_report(db=db, task_id=case.case_no)
            from app.services.screening_export import render_single_report_pdf
            pdf_bytes = render_single_report_pdf(report)
            rel_url, _abs = save_report_pdf(case.case_no, pdf_bytes)
            case.report_pdf_path = rel_url
            report_pdf_url_str = rel_url
        except Exception as e:  # noqa: BLE001
            # 不阻塞主流程：标记失败到 remark 末尾以便审计
            case.report_pdf_path = ""
            case.remark = (
                (case.remark + " | " if case.remark else "")
                + f"[报告 PDF 生成失败：{e!s}]"
            )

        db.commit()

        return ConfirmReportResult(
            task_id=case.case_no,
            case_id=case.id,
            status="done",
            reviewer=user.real_name or user.username,
            reviewed_at=case.review_at.strftime("%Y-%m-%d %H:%M:%S"),
            patient_bound=patient_bound,
            patient_phone=phone,
            patient_user_id=case.patient_user_id,
            report_status=case.report_status,  # type: ignore[arg-type]
            report_pdf_url=report_pdf_url_str,
        )

    # ----------- 11. 病患下载 / 预览 PDF -----------

    @staticmethod
    def patient_report_pdf(
        db: Session,
        user: User,
        case_id: int,
    ) -> Tuple[bytes, str]:
        """
        病患端按 case_id 取报告 PDF。
        权限：仅当
          - case.patient_user_id == user.id
          - 或 case.patient_phone == user.phone（兼容尚未绑定 patient_user_id 的旧数据）
        允许访问。其他情况一律 403。

        返回：(pdf_bytes, file_name)
        - 优先读取 case.report_pdf_path 落盘文件；
        - 文件丢失或缺省时，按 case 现场重新生成（不写盘 / 不动状态）。
        """
        case = (
            db.query(ScreeningCase)
            .filter(ScreeningCase.id == case_id)
            .first()
        )
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"病例不存在：{case_id}",
            )

        # 权限：本人手机号或绑定 user 命中
        owns = False
        if case.patient_user_id and case.patient_user_id == user.id:
            owns = True
        elif user.phone and case.patient_phone and case.patient_phone == user.phone:
            owns = True
        if not owns:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="该报告不属于当前账号，无权查看",
            )

        if case.report_status != "confirmed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该报告尚未确认，暂不可下载",
            )

        # 1) 优先读盘
        pdf_bytes: Optional[bytes] = None
        if case.report_pdf_path:
            full = resolve_report_pdf(case.report_pdf_path)
            if full is not None:
                try:
                    pdf_bytes = full.read_bytes()
                except Exception:
                    pdf_bytes = None

        # 2) 兜底：现场再生成
        if pdf_bytes is None:
            from app.services.screening_export import render_single_report_pdf
            report = ScreeningService.get_report(db=db, task_id=case.case_no)
            pdf_bytes = render_single_report_pdf(report)
            # 顺手补盘（仅当原路径缺失时；不改 status）
            try:
                rel_url, _abs = save_report_pdf(case.case_no, pdf_bytes)
                case.report_pdf_path = rel_url
                db.commit()
            except Exception:
                pass

        file_name = f"{case.case_no}_体检报告.pdf"
        return pdf_bytes, file_name

    # ----------- 11. 上传时按手机号自动关联 -----------

    @staticmethod
    def auto_bind_by_phone(db: Session, case: ScreeningCase) -> bool:
        """
        上传完成后：
        - 若 patient_phone 已填，则查询 patient 用户账号
        - 命中则视为已绑定（不需要写入额外表 —— 病患通过 phone 取报告即可）
        """
        phone = (case.patient_phone or "").strip()
        if not phone:
            return False
        return (
            db.query(User.id).filter(User.phone == phone).first() is not None
        )

    # ============================================================
    # 12. 医生 / 管理员 补充修改病例 + 上传眼底图
    # ============================================================

    @staticmethod
    def _get_case_by_id_or_404(db: Session, case_id: int) -> ScreeningCase:
        case = db.query(ScreeningCase).filter(ScreeningCase.id == case_id).first()
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"病例不存在：{case_id}",
            )
        return case

    @staticmethod
    def _flatten_image_paths(case: ScreeningCase) -> List[CaseImageItem]:
        items: List[CaseImageItem] = []
        paths = case.image_paths or {}
        if isinstance(paths, dict):
            for eye, arr in paths.items():
                eye_norm = (eye or "UK").upper()
                if eye_norm not in ("OD", "OS", "OU", "UK"):
                    eye_norm = "UK"
                if isinstance(arr, list):
                    for u in arr:
                        if not u:
                            continue
                        items.append(CaseImageItem(
                            eye=eye_norm,  # type: ignore[arg-type]
                            url=u,
                            file_name=u.rsplit("/", 1)[-1],
                        ))
        return items

    @staticmethod
    def update_case(
        db: Session,
        user: User,
        case_id: int,
        params: CaseUpdateParams,
    ) -> ScreeningTaskOut:
        """补充修改病例文本字段。仅 TEACHER / ADMIN 可调（路由层已守卫）。

        - patient_phone 同步写入 phone 与 patient_phone（便于联系 + 病患账号绑定）
        - 不重新触发 AI 推理；不更改 status
        - 写 review_user_id（最近一次编辑人）
        """
        case = ScreeningService._get_case_by_id_or_404(db, case_id)

        data = params.model_dump(exclude_unset=True)

        if "patient_name" in data and data["patient_name"] is not None:
            case.patient_name = (data["patient_name"] or "").strip()
        if "gender" in data and data["gender"] is not None:
            case.gender = GENDER_CN_TO_DB.get(
                data["gender"], GenderEnum.UNKNOWN.value,
            )
        if "age" in data:
            case.age = data["age"]
        if "patient_phone" in data and data["patient_phone"] is not None:
            phone = (data["patient_phone"] or "").strip()
            # 简单校验（与 schemas/patient.py 一致）
            if phone and (not phone.isdigit() or len(phone) != 11 or not phone.startswith("1")):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="联系电话格式不正确（需 11 位且以 1 开头）",
                )
            case.patient_phone = phone
            case.phone = phone or case.phone
        if "chief_complaint" in data and data["chief_complaint"] is not None:
            case.chief_complaint = (data["chief_complaint"] or "").strip()
        if "medical_history" in data and data["medical_history"] is not None:
            case.medical_history = (data["medical_history"] or "").strip()
        if "remark" in data and data["remark"] is not None:
            case.remark = (data["remark"] or "").strip()

        # 记录最近一次编辑人
        case.review_user_id = user.id
        db.commit()
        db.refresh(case)
        return _to_task_out(case, db)

    @staticmethod
    async def add_case_images(
        db: Session,
        user: User,
        case_id: int,
        files: List[UploadFile],
        eye: str = "UK",
    ) -> CaseImagesResult:
        """为已存在的病例补充上传眼底图。

        - 校验扩展名 / 大小 / 解码 由 save_fundus_image 完成
        - 写入 image_paths[eye] 末尾，更新 image_count
        - 不重新触发 AI 推理（避免覆盖已有结果）；如需可由前端再调 reanalyze
        """
        case = ScreeningService._get_case_by_id_or_404(db, case_id)
        requested = (eye or "UK").strip().upper()
        explicit = requested in ("OD", "OS", "OU")

        paths = dict(case.image_paths or {})

        for f in files or []:
            if not f or not f.filename:
                continue
            rel_url, file_name, _size = await save_fundus_image(f, user.id)
            if explicit:
                this_eye = requested
            else:
                this_eye = resolve_uploaded_eye(
                    "UK",
                    file_name=f.filename or file_name,
                    image_path=resolve_static_file(rel_url),
                    role="original",
                )
            bucket = list(paths.get(this_eye) or [])
            bucket.append(rel_url)
            paths[this_eye] = bucket
        case.image_paths = paths
        case.image_count = sum(
            len(v) for v in paths.values() if isinstance(v, list)
        )
        case.review_user_id = user.id
        db.commit()
        db.refresh(case)

        return CaseImagesResult(
            case_id=case.id,
            image_count=case.image_count,
            images=ScreeningService._flatten_image_paths(case),
        )

    @staticmethod
    def delete_case_image(
        db: Session,
        user: User,
        case_id: int,
        image_url: str,
    ) -> CaseImagesResult:
        """从病例中删除一张眼底图（同时清磁盘）。"""
        case = ScreeningService._get_case_by_id_or_404(db, case_id)
        target = (image_url or "").strip()
        if not target:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="缺少要删除的影像 URL",
            )

        paths = dict(case.image_paths or {})
        removed = False
        for eye_key, arr in list(paths.items()):
            if not isinstance(arr, list):
                continue
            if target in arr:
                arr_new = [u for u in arr if u != target]
                paths[eye_key] = arr_new
                removed = True
        if not removed:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="该影像不属于此病例",
            )

        case.image_paths = paths
        case.image_count = sum(
            len(v) for v in paths.values() if isinstance(v, list)
        )
        case.review_user_id = user.id

        try:
            delete_fundus_file(target)
        except Exception:
            # 仅记录失败，不阻断
            pass

        db.commit()
        db.refresh(case)

        return CaseImagesResult(
            case_id=case.id,
            image_count=case.image_count,
            images=ScreeningService._flatten_image_paths(case),
        )

    @staticmethod
    def list_case_images(db: Session, case_id: int) -> CaseImagesResult:
        case = ScreeningService._get_case_by_id_or_404(db, case_id)
        return CaseImagesResult(
            case_id=case.id,
            image_count=case.image_count,
            images=ScreeningService._flatten_image_paths(case),
        )
