# -*- coding: utf-8 -*-
"""批量导入：登记表、左右眼命名、质量、重复、患者信息。"""

import io
import shutil

from fastapi import HTTPException
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.common.utils import screening_dir
from app.db.base import Base
from app.db.models import Role, RoleEnum, TrainingCase, User
from app.services.case_import_service import CaseImportService, _fingerprint, _stage_root


def _db():
    eng = create_engine("sqlite://")
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)()


def _user(db, code):
    role = Role(code=code, name=code)
    db.add(role)
    db.flush()
    user = User(username=code.lower(), password_hash="x", real_name="测试", role_id=role.id)
    db.add(user)
    db.commit()
    return user


def _png(side: int, color=(40, 80, 60)) -> bytes:
    img = Image.new("RGB", (side, side), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _sheet(lines: str) -> bytes:
    head = "登记号,标题,病种,难度,年龄,性别,眼别,临床信息\n"
    return (head + lines).encode("utf-8")


def test_template_has_no_patient_identity_columns():
    text = CaseImportService.template()
    assert "登记号" in text and "眼别" in text
    assert "姓名" not in text.splitlines()[0]
    assert "手机" not in text.splitlines()[0]
    assert "身份证" not in text.splitlines()[0]


def test_rejects_phone_eye_mismatch_and_tiny_image():
    db = _db()
    teacher = _user(db, RoleEnum.TEACHER.value)
    sheet = _sheet(
        "P001,教学例,糖尿病视网膜病变,入门,60,女,右眼,联系13812345678\n"
        "P002,另一例,正常,入门,40,男,右眼,病史\n"
        "P003,过小,正常,入门,40,男,左眼,病史\n"
    )
    report = CaseImportService.check(
        db,
        teacher,
        sheet,
        [
            ("P001_右眼.png", _png(480, (20, 20, 20))),
            ("P002_左眼.png", _png(480, (90, 40, 40))),
            ("P003_左眼.png", _png(80, (90, 40, 40))),
        ],
    )
    by_no = {row["registerNo"]: row for row in report["rows"]}
    assert by_no["P001"]["ok"] is False
    assert any("手机号" in item for item in by_no["P001"]["issues"])
    assert by_no["P002"]["ok"] is False
    assert any("不一致" in item for item in by_no["P002"]["issues"])
    assert by_no["P003"]["ok"] is False
    assert any("过小" in item for item in by_no["P003"]["issues"])
    assert report["token"] == ""
    db.close()


def test_duplicate_image_and_identity_header_are_blocked():
    db = _db()
    teacher = _user(db, RoleEnum.TEACHER.value)
    same = _png(480, (12, 80, 30))
    report = CaseImportService.check(
        db,
        teacher,
        _sheet("D001,甲,正常,入门,50,女,右眼,病史\nD002,乙,正常,入门,50,女,右眼,病史\n"),
        [("D001_右眼.png", same), ("D002_OD.png", same)],
    )
    by_no = {row["registerNo"]: row for row in report["rows"]}
    assert by_no["D001"]["ok"] is True
    assert by_no["D002"]["ok"] is False
    assert any("重复" in item for item in by_no["D002"]["issues"])
    if report["token"]:
        shutil.rmtree(_stage_root() / report["token"], ignore_errors=True)

    try:
        CaseImportService.check(
            db,
            teacher,
            "登记号,姓名,眼别\nX1,张三,右眼\n".encode("utf-8"),
            [],
        )
        raise AssertionError("含姓名列的表应被拒绝")
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "姓名" in exc.detail
    db.close()


def test_library_duplicate_uses_existing_case(monkeypatch):
    db = _db()
    teacher = _user(db, RoleEnum.TEACHER.value)
    raw = _png(480, (70, 10, 10))
    monkeypatch.setattr(
        "app.services.case_import_service._existing_hashes",
        lambda _db: {_fingerprint(raw): "T2026001"},
    )
    report = CaseImportService.check(
        db,
        teacher,
        _sheet("L001,重复例,正常,入门,50,女,右眼,病史\n"),
        [("L001_右眼.png", raw)],
    )
    assert report["rows"][0]["ok"] is False
    assert "T2026001" in report["rows"][0]["issues"][0]
    db.close()


def test_commit_writes_unpublished_draft_without_patient_identity():
    db = _db()
    teacher = _user(db, RoleEnum.TEACHER.value)
    report = CaseImportService.check(
        db,
        teacher,
        _sheet("C001,左右眼教学,青光眼,中级,55,男,左右眼,仅病史\n"),
        [
            ("C001_右眼.png", _png(480, (30, 30, 80))),
            ("C001_左眼.png", _png(480, (80, 30, 30))),
        ],
    )
    assert report["passed"] == 1
    saved = []
    try:
        created = CaseImportService.commit(db, teacher, report["token"])
        assert created["count"] == 1
        case = db.query(TrainingCase).filter(TrainingCase.id == created["created"][0]["id"]).one()
        saved.extend((case.image_paths or {}).get("OD") or [])
        saved.extend((case.image_paths or {}).get("OS") or [])
        assert case.is_published is False
        assert case.is_train_case is False
        assert case.patient_name == ""
        assert case.patient_phone == ""
        assert case.patient_age == 55
        assert case.patient_gender == "M"
        assert "OD" in case.image_paths and "OS" in case.image_paths
        student = _user(db, RoleEnum.STUDENT.value)
        try:
            CaseImportService.commit(db, student, "abcdefgh")
            raise AssertionError("学员不能导入")
        except HTTPException as exc:
            assert exc.status_code == 403
    finally:
        for url in saved:
            name = url.rsplit("/", 1)[-1]
            (screening_dir() / name).unlink(missing_ok=True)
        db.close()
