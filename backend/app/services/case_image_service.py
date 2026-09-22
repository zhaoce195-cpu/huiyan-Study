"""
病例影像（一对多）业务层
"""

from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.common.eye_infer import resolve_static_file, resolve_uploaded_eye
from app.common.utils import (
    delete_fundus_file,
    save_fundus_image,
)
from app.db.models import (
    CaseImage,
    CaseImageRoleEnum,
    CaseImageTableEnum,
    REQUIRED_ROLES_IDRID,
    RoleEnum,
    ScreeningCase,
    TrainingCase,
    User,
)
from app.schemas.case_image import (
    CaseImageOut,
    CaseImagesGrouped,
    IncompleteCaseRow,
)


ROLE_TEXT: Dict[str, str] = {
    "original": "原始眼底图",
    "MA": "微血管瘤",
    "HE": "出血",
    "EX": "硬性渗出",
    "SE": "软性渗出",
    "OD": "视盘",
    "color_mask": "彩色多病灶 mask",
    "overlay": "金标准叠加",
    "class_mask": "类别 mask",
    "other": "其它",
}


def _validate_role(role: str) -> str:
    valid = {r.value for r in CaseImageRoleEnum}
    if role not in valid:
        raise HTTPException(400, detail=f"非法影像 role：{role}")
    return role


def _validate_table(case_table: str) -> str:
    valid = {t.value for t in CaseImageTableEnum}
    if case_table not in valid:
        raise HTTPException(400, detail=f"非法 caseTable：{case_table}")
    return case_table


def _validate_eye(eye: str) -> str:
    if eye not in ("OD", "OS", "OU", "UK"):
        raise HTTPException(400, detail=f"非法 eye：{eye}")
    return eye


def _get_case(db: Session, case_table: str, case_id: int):
    if case_table == "screening":
        c = db.query(ScreeningCase).filter(ScreeningCase.id == case_id).first()
    elif case_table == "training":
        c = db.query(TrainingCase).filter(TrainingCase.id == case_id).first()
    else:
        raise HTTPException(400, detail="无效 case_table")
    if not c:
        raise HTTPException(404, detail=f"病例不存在：{case_table}#{case_id}")
    return c


def _is_teacher_or_admin(user: User) -> bool:
    role_code = user.role.code if user.role else ""
    return role_code in (RoleEnum.TEACHER.value, RoleEnum.ADMIN.value)


def _single_original_eye(db: Session, case_table: str, case_id: int) -> str:
    """该病例原图只有一种明确眼别时返回它，供 mask / 标注层继承。"""
    rows = (
        db.query(CaseImage.eye)
        .filter(
            CaseImage.case_table == case_table,
            CaseImage.case_id == case_id,
            CaseImage.role == "original",
        )
        .all()
    )
    eyes = set()
    for (value,) in rows:
        code = (value or "").upper()
        if code in ("OD", "OS", "OU"):
            eyes.add(code)
    if len(eyes) == 1:
        return next(iter(eyes))
    return ""


def _append_original_path(case, eye: str, rel_url: str) -> None:
    """原图写入 image_paths 的对应眼别桶，避免新图继续落在过期的 OU 桶。"""
    if not hasattr(case, "image_paths"):
        return
    paths = dict(case.image_paths or {})
    bucket = [u for u in (paths.get(eye) or []) if u]
    if rel_url not in bucket:
        bucket.append(rel_url)
    paths[eye] = bucket
    case.image_paths = paths
    if hasattr(case, "image_count"):
        case.image_count = sum(
            len(v) for v in paths.values() if isinstance(v, list)
        )


def _to_out(item: CaseImage) -> CaseImageOut:
    uploader_name = ""
    if item.uploader is not None:
        uploader_name = item.uploader.real_name or item.uploader.username or ""
    return CaseImageOut(
        id=item.id,
        case_table=item.case_table,  # type: ignore[arg-type]
        case_id=item.case_id,
        role=item.role,  # type: ignore[arg-type]
        role_text=ROLE_TEXT.get(item.role, item.role),
        eye=item.eye,  # type: ignore[arg-type]
        file_url=item.file_url,
        file_name=item.file_name or "",
        file_size=item.file_size or 0,
        width=item.width or 0,
        height=item.height or 0,
        sort_order=item.sort_order or 0,
        uploaded_by=item.uploaded_by,
        uploader_name=uploader_name,
        created_at=item.created_at,
    )


class CaseImageService:

    # ---------------- 查询 ----------------

    @staticmethod
    def list_by_case(
        db: Session,
        *,
        case_table: str,
        case_id: int,
        roles_filter: Optional[List[str]] = None,
    ) -> List[CaseImage]:
        _validate_table(case_table)
        q = db.query(CaseImage).filter(
            CaseImage.case_table == case_table,
            CaseImage.case_id == case_id,
        )
        if roles_filter:
            q = q.filter(CaseImage.role.in_(roles_filter))
        return (
            q.order_by(CaseImage.role.asc(), CaseImage.sort_order.asc(), CaseImage.id.asc()).all()
        )

    @staticmethod
    def grouped(
        db: Session,
        *,
        case_table: str,
        case_id: int,
        roles_filter: Optional[List[str]] = None,
    ) -> CaseImagesGrouped:
        case = _get_case(db, case_table, case_id)
        items = CaseImageService.list_by_case(
            db, case_table=case_table, case_id=case_id, roles_filter=roles_filter,
        )
        groups: Dict[str, List[str]] = defaultdict(list)
        for it in items:
            groups[it.role].append(it.file_url)
        comp = CaseImageService.case_completeness(db, case_table=case_table, case_id=case_id)
        return CaseImagesGrouped(
            case_table=case_table,  # type: ignore[arg-type]
            case_id=case_id,
            case_sn=getattr(case, "case_sn", "") or "",
            case_no=getattr(case, "case_no", "") or "",
            image_groups=groups,  # type: ignore[arg-type]
            items=[_to_out(i) for i in items],
            image_complete=comp["complete"],
            missing_roles=comp["missing_roles"],  # type: ignore[arg-type]
        )

    # ---------------- 完整性 ----------------

    @staticmethod
    def case_completeness(
        db: Session, *, case_table: str, case_id: int,
        required: Optional[List[str]] = None,
    ) -> Dict[str, object]:
        required = list(required or REQUIRED_ROLES_IDRID)
        _validate_table(case_table)
        roles_present = {
            r for (r,) in db.query(CaseImage.role)
            .filter(
                CaseImage.case_table == case_table,
                CaseImage.case_id == case_id,
            )
            .distinct()
            .all()
        }
        missing = [r for r in required if r not in roles_present]
        return {"complete": not missing, "missing_roles": missing}

    @staticmethod
    def list_incomplete(
        db: Session, *, case_table: str = "training",
        page: int = 1, page_size: int = 20,
    ) -> Tuple[int, List[IncompleteCaseRow]]:
        _validate_table(case_table)
        # 查全部 case_id（该业务表下有影像记录的）
        Model = TrainingCase if case_table == "training" else ScreeningCase
        all_cases = db.query(Model).order_by(Model.id.desc()).all()
        rows: List[IncompleteCaseRow] = []
        for c in all_cases:
            comp = CaseImageService.case_completeness(
                db, case_table=case_table, case_id=c.id,
            )
            if not comp["complete"]:
                count = (
                    db.query(CaseImage)
                    .filter(
                        CaseImage.case_table == case_table,
                        CaseImage.case_id == c.id,
                    )
                    .count()
                )
                rows.append(IncompleteCaseRow(
                    case_table=case_table,  # type: ignore[arg-type]
                    case_id=c.id,
                    case_no=getattr(c, "case_no", "") or "",
                    case_sn=getattr(c, "case_sn", "") or "",
                    title=getattr(c, "title", "") or "",
                    missing_roles=comp["missing_roles"],  # type: ignore[arg-type]
                    image_count=count,
                ))
        total = len(rows)
        start = max(0, (page - 1) * page_size)
        end = start + page_size
        return total, rows[start:end]

    # ---------------- 写入：上传 ----------------

    @staticmethod
    async def add_upload(
        db: Session, *,
        user: User,
        case_table: str,
        case_id: int,
        file: UploadFile,
        role: str,
        eye: str = "UK",
    ) -> CaseImage:
        if not _is_teacher_or_admin(user):
            raise HTTPException(403, detail="仅医生 / 管理员可上传影像")
        _validate_table(case_table)
        _validate_role(role)
        eye_in = _validate_eye((eye or "UK").strip().upper() or "UK")
        case = _get_case(db, case_table, case_id)
        rel_url, file_name, size = await save_fundus_image(file, user.id)
        inherited = ""
        if eye_in not in ("OD", "OS", "OU") and role != "original":
            inherited = _single_original_eye(db, case_table, case_id)
        eye_out = resolve_uploaded_eye(
            eye_in,
            file_name=file.filename or "",
            image_path=resolve_static_file(rel_url),
            role=role,
            inherited=inherited,
        )
        if role == "original":
            _append_original_path(case, eye_out, rel_url)
        rec = CaseImage(
            case_table=case_table, case_id=case_id,
            role=role, eye=eye_out,
            file_url=rel_url, file_name=file_name, file_size=size,
            uploaded_by=user.id,
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)
        return rec

    # ---------------- 写入：登记已有文件（导入脚本用） ----------------

    @staticmethod
    def register_external(
        db: Session, *,
        case_table: str, case_id: int,
        role: str, eye: str = "UK",
        file_url: str, file_name: str = "",
        file_size: int = 0, width: int = 0, height: int = 0,
        uploaded_by: Optional[int] = None,
    ) -> CaseImage:
        _validate_table(case_table)
        _validate_role(role)
        _validate_eye(eye)
        # 同一 file_url 已登记 → 跳过
        existing = (
            db.query(CaseImage)
            .filter(
                CaseImage.case_table == case_table,
                CaseImage.case_id == case_id,
                CaseImage.role == role,
                CaseImage.file_url == file_url,
            )
            .first()
        )
        if existing:
            return existing
        rec = CaseImage(
            case_table=case_table, case_id=case_id,
            role=role, eye=eye,
            file_url=file_url, file_name=file_name, file_size=file_size,
            width=width, height=height,
            uploaded_by=uploaded_by,
        )
        db.add(rec)
        db.flush()
        return rec

    # ---------------- 删除 ----------------

    @staticmethod
    def delete(db: Session, *, image_id: int, user: User) -> None:
        if not _is_teacher_or_admin(user):
            raise HTTPException(403, detail="仅医生 / 管理员可删除影像")
        rec = db.query(CaseImage).filter(CaseImage.id == image_id).first()
        if not rec:
            raise HTTPException(404, detail="影像不存在")
        url = rec.file_url
        db.delete(rec)
        db.commit()
        try:
            delete_fundus_file(url)
        except Exception:
            pass


__all__ = ["CaseImageService", "ROLE_TEXT"]
