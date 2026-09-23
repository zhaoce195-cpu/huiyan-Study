# -*- coding: utf-8 -*-
"""教师批量登记教学病例。先检查，通过的才入库为未发布草稿。"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import HTTPException, status
from PIL import Image, ImageOps, ImageStat
from sqlalchemy.orm import Session

from app.common.eye_infer import resolve_static_file
from app.common.utils import project_root, screening_dir, screening_url
from app.core.config import settings
from app.db.models import TrainingCase, User
from app.db.models.user import RoleEnum

TEMPLATE = (
    "登记号,标题,病种,难度,年龄,性别,眼别,临床信息,病人编号,检查日期\n"
    "A001,眼底教学例,糖尿病视网膜病变,入门,60,女,右眼,仅写病史，不要写姓名手机号身份证号,P-01,2024-03-01\n"
    "A002,同一病人半年后,糖尿病视网膜病变,入门,60,女,右眼,仅写病史，不要写姓名手机号身份证号,P-01,2024-09-01\n"
)

NAMING = (
    "影像文件名必须是「登记号_右眼」「登记号_左眼」或「登记号_双眼」，"
    "也可以用 _OD / _OS / _OU。眼别列要和文件名一致。"
    "左右眼都有时，眼别填「左右眼」，并各传一张。"
    "登记表不要出现姓名、手机号、身份证号。"
    "公共数据集通常一行一张图，病人编号和检查日期留空即可。"
    "同一个病人不同时期要分成多行：登记号不同，病人编号相同，各自填写检查日期。"
    "没有日期就留空，不要编造。"
)

_EYE_WORD = {
    "右眼": "OD",
    "OD": "OD",
    "左眼": "OS",
    "OS": "OS",
    "双眼": "OU",
    "OU": "OU",
}
_BOTH = {"左右眼", "双眼都有", "OD+OS", "OS+OD"}
_CATEGORY = {
    "糖尿病视网膜病变": "DR",
    "DR": "DR",
    "正常": "NORMAL",
    "正常眼底": "NORMAL",
    "NORMAL": "NORMAL",
    "青光眼": "GLAUCOMA",
    "GLAUCOMA": "GLAUCOMA",
    "黄斑": "AMD",
    "老年性黄斑变性": "AMD",
    "AMD": "AMD",
    "高血压": "HYPERTENSION",
    "高血压眼底": "HYPERTENSION",
    "HYPERTENSION": "HYPERTENSION",
    "其他": "OTHER",
    "OTHER": "OTHER",
}
_DIFFICULTY = {
    "入门": "EASY",
    "简单": "EASY",
    "EASY": "EASY",
    "中级": "MEDIUM",
    "MEDIUM": "MEDIUM",
    "高级": "HARD",
    "HARD": "HARD",
}
_GENDER = {"男": "M", "女": "F", "未知": "U", "M": "M", "F": "F", "U": "U", "": "U"}
_PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_IDCARD = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")
_FORBIDDEN_HEADER = ("姓名", "患者名", "手机", "电话", "身份证")
_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
_MIN_SIDE = 400


def _teacher(user: User) -> None:
    code = user.role.code if user.role else ""
    if code not in (RoleEnum.TEACHER.value, RoleEnum.ADMIN.value):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "只有教师可以批量导入病例")


def _stage_root() -> Path:
    path = project_root() / settings.UPLOAD_DIR / "uploads" / "case-import"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _phi(text: str) -> Optional[str]:
    if _PHONE.search(text or ""):
        return "含有手机号，患者信息还没去掉"
    if _IDCARD.search(text or ""):
        return "含有身份证号，患者信息还没去掉"
    return None


def _eye_from_name(filename: str) -> Optional[str]:
    stem = Path(filename or "").stem
    for suffix, eye in (
        ("_右眼", "OD"),
        ("_左眼", "OS"),
        ("_双眼", "OU"),
        ("_OD", "OD"),
        ("_OS", "OS"),
        ("_OU", "OU"),
    ):
        if stem.upper().endswith(suffix.upper()):
            return eye
    return None


def _register_from_name(filename: str) -> str:
    stem = Path(filename or "").stem
    for suffix in ("_右眼", "_左眼", "_双眼", "_OD", "_OS", "_OU"):
        if stem.upper().endswith(suffix.upper()):
            return stem[: -len(suffix)]
    return stem


def _quality(raw: bytes) -> Optional[str]:
    try:
        img = Image.open(io.BytesIO(raw))
        img = ImageOps.exif_transpose(img) or img
        img.load()
    except Exception:
        return "图像无法读取"
    width, height = img.size
    if min(width, height) < _MIN_SIDE:
        return f"图像过小（{width}×{height}），不足以入库"
    gray = img.convert("L")
    mean = ImageStat.Stat(gray).mean[0]
    if mean < 12:
        return "图像过暗，质量不足以入库"
    if mean > 248:
        return "图像过曝，质量不足以入库"
    return None


def _fingerprint(raw: bytes) -> Optional[str]:
    """缩小后比像素。同一张图重新编码成 webp 仍能对上库里的文件。"""
    try:
        img = Image.open(io.BytesIO(raw))
        img = ImageOps.exif_transpose(img) or img
        img = img.convert("RGB").resize((32, 32))
    except Exception:
        return None
    return hashlib.sha256(img.tobytes()).hexdigest()


def _existing_hashes(db: Session) -> Dict[str, str]:
    found: Dict[str, str] = {}
    rows = db.query(TrainingCase.id, TrainingCase.case_no, TrainingCase.image_paths).all()
    for _case_id, case_no, paths in rows:
        if not isinstance(paths, dict):
            continue
        for urls in paths.values():
            if not isinstance(urls, list):
                continue
            for url in urls:
                path = resolve_static_file(url or "")
                if path is None:
                    continue
                try:
                    digest = _fingerprint(path.read_bytes())
                except OSError:
                    continue
                if digest:
                    found.setdefault(digest, case_no)
    return found


def _read_sheet(raw: bytes) -> List[dict]:
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "登记表是空的")
    headers = [name.strip() for name in reader.fieldnames if name]
    for name in headers:
        if any(word in name for word in _FORBIDDEN_HEADER):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"登记表不能包含「{name}」。患者信息要先去掉，只保留登记号和教学信息。",
            )
    required = {"登记号", "标题", "眼别"}
    missing = required - set(headers)
    if missing:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"登记表缺少列：{'、'.join(sorted(missing))}")
    rows = []
    for row in reader:
        register = (row.get("登记号") or "").strip()
        if not register or register.startswith("#"):
            continue
        rows.append({key.strip(): (value or "").strip() for key, value in row.items() if key})
    if not rows:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "登记表没有可导入的行")
    return rows


def _save_webp(raw: bytes, user_id: int) -> str:
    img = Image.open(io.BytesIO(raw))
    img = ImageOps.exif_transpose(img) or img
    max_side = 2048
    if max(img.size) > max_side:
        ratio = max_side / max(img.size)
        img = img.resize((int(img.size[0] * ratio), int(img.size[1] * ratio)), Image.LANCZOS)
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    save_name = f"f{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}.webp"
    path = screening_dir() / save_name
    img.save(path, format="WEBP", quality=90, method=6)
    return screening_url(save_name)


class CaseImportService:

    @staticmethod
    def require_teacher(user: User) -> None:
        _teacher(user)

    @staticmethod
    def template() -> str:
        return TEMPLATE

    @staticmethod
    def check(db: Session, user: User, sheet: bytes, files: List[tuple]) -> dict:
        _teacher(user)
        rows = _read_sheet(sheet)
        known = _existing_hashes(db)
        grouped: Dict[str, List[dict]] = {}
        for filename, raw in files:
            suffix = Path(filename).suffix.lower()
            if suffix not in _IMAGE_EXT:
                continue
            register = _register_from_name(filename)
            grouped.setdefault(register, []).append({
                "filename": filename,
                "raw": raw,
                "eye": _eye_from_name(filename),
                "digest": _fingerprint(raw),
            })

        seen_register = set()
        seen_digest: Dict[str, str] = {}
        report = []
        staged = []
        for row in rows:
            register = row.get("登记号") or ""
            issues = []
            if register in seen_register:
                issues.append("登记号在表里重复")
            seen_register.add(register)
            blob = " ".join([
                register,
                row.get("标题") or "",
                row.get("临床信息") or "",
                row.get("病种") or "",
            ])
            phi = _phi(blob)
            if phi:
                issues.append(phi)
            eye_text = row.get("眼别") or ""
            exam_on = (row.get("检查日期") or "").strip()
            if exam_on:
                try:
                    datetime.strptime(exam_on, "%Y-%m-%d")
                except ValueError:
                    issues.append("检查日期请写成 2024-03-01。没有日期就留空，不要编造")
            subject_no = (row.get("病人编号") or "").strip()
            if _phi(subject_no):
                issues.append("病人编号不要填手机号或身份证号")
            both = eye_text in _BOTH
            wanted = _EYE_WORD.get(eye_text)
            if not both and wanted is None:
                issues.append("眼别请填右眼、左眼、双眼或左右眼")
            images = grouped.get(register, [])
            if not images:
                issues.append("没有找到对应影像。文件名要用登记号加眼别")
            eyes = []
            for image in images:
                if image["eye"] is None:
                    issues.append(f"{image['filename']} 没有按命名标明左右眼")
                    continue
                if not both and wanted and image["eye"] != wanted:
                    issues.append(f"{image['filename']} 的眼别和登记表不一致")
                if both and image["eye"] not in ("OD", "OS"):
                    issues.append(f"{image['filename']} 左右眼病例请分别用右眼和左眼")
                name_phi = _phi(image["filename"])
                if name_phi:
                    issues.append(f"{image['filename']} {name_phi}")
                quality = _quality(image["raw"])
                if quality:
                    issues.append(f"{image['filename']} {quality}")
                if image["digest"]:
                    previous = seen_digest.get(image["digest"]) or known.get(image["digest"])
                    if previous:
                        issues.append(f"{image['filename']} 与已有影像重复（{previous}）")
                    seen_digest[image["digest"]] = register
                eyes.append(image["eye"])
            if both and images and not ({"OD", "OS"} <= set(eyes)):
                issues.append("眼别填了左右眼，但右眼或左眼影像不齐")
            ok = not issues
            report.append({
                "registerNo": register,
                "title": row.get("标题") or "",
                "eyes": eyes,
                "ok": ok,
                "issues": issues,
            })
            if ok:
                staged.append({
                    "register_no": register,
                    "title": (row.get("标题") or register)[:128],
                    "category": _CATEGORY.get(row.get("病种") or "", "OTHER"),
                    "difficulty": _DIFFICULTY.get(row.get("难度") or "", "EASY"),
                    "age": row.get("年龄") or "",
                    "gender": _GENDER.get(row.get("性别") or "", "U"),
                    "clinical": (row.get("临床信息") or "")[:2000],
                    "subject_no": (row.get("病人编号") or "").strip()[:32],
                    "exam_on": (row.get("检查日期") or "").strip(),
                    "files": [
                        {"eye": image["eye"], "raw": image["raw"]}
                        for image in images
                        if image["eye"]
                    ],
                })

        token = ""
        if staged:
            token = uuid.uuid4().hex
            folder = _stage_root() / token
            folder.mkdir(parents=True, exist_ok=True)
            manifest_rows = []
            for index, item in enumerate(staged):
                saved = []
                for file_index, image in enumerate(item["files"]):
                    name = f"{index}_{file_index}.bin"
                    (folder / name).write_bytes(image["raw"])
                    saved.append({"eye": image["eye"], "file": name})
                manifest_rows.append({**{k: v for k, v in item.items() if k != "files"}, "files": saved})
            (folder / "manifest.json").write_text(
                json.dumps({"user_id": user.id, "rows": manifest_rows}, ensure_ascii=False),
                encoding="utf-8",
            )
        return {
            "token": token,
            "naming": NAMING,
            "total": len(report),
            "passed": sum(1 for item in report if item["ok"]),
            "failed": sum(1 for item in report if not item["ok"]),
            "rows": report,
        }

    @staticmethod
    def commit(db: Session, user: User, token: str) -> dict:
        _teacher(user)
        folder = _stage_root() / (token or "").strip()
        manifest_path = folder / "manifest.json"
        if not manifest_path.is_file():
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "检查结果已失效，请重新上传")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("user_id") != user.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "不能提交别人的导入")
        from sqlalchemy import func
        year = datetime.now().strftime("%Y")
        prefix = f"T{year}"
        count = (
            db.query(func.count(TrainingCase.id))
            .filter(TrainingCase.case_no.like(f"{prefix}%"))
            .scalar()
        ) or 0
        created = []
        for offset, item in enumerate(manifest.get("rows") or [], start=1):
            paths: Dict[str, List[str]] = {}
            for image in item.get("files") or []:
                raw = (folder / image["file"]).read_bytes()
                url = _save_webp(raw, user.id)
                paths.setdefault(image["eye"], []).append(url)
            age_text = str(item.get("age") or "").strip()
            age = int(age_text) if age_text.isdigit() else None
            case_no = f"{prefix}{count + offset:03d}"
            case = TrainingCase(
                case_no=case_no,
                title=item.get("title") or item.get("register_no") or case_no,
                description="批量导入的教学草稿，请补金标准后再发布。",
                category=item.get("category") or "OTHER",
                difficulty=item.get("difficulty") or "EASY",
                patient_name="",
                patient_age=age,
                patient_gender=item.get("gender") or "U",
                patient_phone="",
                subject_no=(item.get("subject_no") or "")[:32],
                exam_on=item.get("exam_on") or "",
                clinical_info=item.get("clinical") or "",
                image_paths=paths,
                gold_dr_grade="",
                gold_diagnosis="",
                teaching_points="",
                is_published=False,
                is_train_case=False,
                creator_id=user.id,
            )
            db.add(case)
            db.flush()
            created.append({"id": case.id, "caseNo": case.case_no, "title": case.title})
        db.commit()
        for child in folder.glob("*"):
            child.unlink(missing_ok=True)
        folder.rmdir()
        return {"created": created, "count": len(created)}
