# -*- coding: utf-8 -*-
"""
IDRiD 批量导入：Dry-run 只扫描、正式入库默认未发布。

流程：
    运维把数据集放到服务器约定目录
        → Dry-run + limit 5：只扫描不写库
        → 取消 Dry-run：正式入库（is_published / is_train_case 均为 False）
        → 病例库完善金标准 / 加入实训后再给学生
"""

from pathlib import Path

import pytest
from fastapi import HTTPException
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import Role, RoleEnum, ScreeningCase, TrainingCase, User
from app.schemas.case_browse import CaseBrowseQuery
from app.services.case_browse_service import CaseBrowseService
from app.services.idrid_import_service import probe_idrid_source, run_idrid_import
from app.services.practice_service import _ensure_case_visible


@pytest.fixture()
def db():
    eng = create_engine("sqlite://")
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture()
def admin(db):
    role = Role(code=RoleEnum.ADMIN.value, name="管理员")
    student_role = Role(code=RoleEnum.STUDENT.value, name="住培医师")
    db.add_all([role, student_role])
    db.flush()
    user = User(username="admin", password_hash="x", role_id=role.id)
    student = User(username="student", password_hash="x", role_id=student_role.id)
    db.add_all([user, student])
    db.commit()
    return {"admin": user, "student": student}


def _tiny_jpg(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (8, 8), (20, 20, 20)).save(path, format="JPEG")


def make_idrid_tree(root: Path, n: int = 6) -> Path:
    """最小可用 IDRiD 目录：3 个必备子目录 + n 张训练原图。"""
    img_dir = root / "1. Original Images" / "a. Training Set"
    gt_root = root / "2. All Segmentation Groundtruths" / "a. Training Set"
    proc = root / "3. IDRID_4_lesion_processed"
    for folder in (
        "1. Microaneurysms",
        "2. Haemorrhages",
        "3. Hard Exudates",
        "4. Soft Exudates",
        "5. Optic Disc",
    ):
        (gt_root / folder).mkdir(parents=True, exist_ok=True)
    (proc / "overlay_on_image" / "a. Training Set").mkdir(parents=True, exist_ok=True)
    (proc / "class_index_mask" / "a. Training Set").mkdir(parents=True, exist_ok=True)
    (proc / "color_mask" / "a. Training Set").mkdir(parents=True, exist_ok=True)
    for i in range(1, n + 1):
        _tiny_jpg(img_dir / f"IDRiD_{i:02d}.jpg")
    return root


def test_probe_missing_dir(tmp_path):
    missing = tmp_path / "no-such"
    out = probe_idrid_source(str(missing))
    assert out.exists is False
    assert out.ready is False
    assert out.image_count == 0
    assert "没有这个目录" in out.hint


def test_probe_ready_tree(tmp_path):
    src = make_idrid_tree(tmp_path / "idrid", n=6)
    out = probe_idrid_source(str(src))
    assert out.exists is True
    assert out.ready is True
    assert out.image_count == 6
    assert out.train_count == 6
    assert out.test_count == 0


def test_dry_run_limit_5_does_not_write(db, admin, tmp_path):
    src = make_idrid_tree(tmp_path / "idrid", n=6)
    dest = tmp_path / "dest"

    out = run_idrid_import(
        db,
        source_path=str(src),
        limit=5,
        dry_run=True,
        creator=admin["admin"],
        dest_root=dest,
    )

    assert out.dry_run is True
    assert out.imported_cases == 5
    assert out.appended_images == 0
    assert db.query(TrainingCase).count() == 0
    assert db.query(ScreeningCase).count() == 0
    assert not dest.exists()


def test_real_import_unpublished_and_student_hidden(db, admin, tmp_path):
    src = make_idrid_tree(tmp_path / "idrid", n=6)
    dest = tmp_path / "dest"

    out = run_idrid_import(
        db,
        source_path=str(src),
        limit=5,
        dry_run=False,
        creator=admin["admin"],
        dest_root=dest,
    )

    assert out.dry_run is False
    assert out.imported_cases == 5
    assert out.appended_images > 0

    cases = db.query(TrainingCase).order_by(TrainingCase.id).all()
    assert len(cases) == 5
    for case in cases:
        assert case.is_published is False
        assert case.is_train_case is False
        assert case.case_no.startswith("IDRID-T-")
        assert dest.joinpath("originals").exists()

    with pytest.raises(HTTPException) as exc:
        CaseBrowseService.get_detail(db, user=admin["student"], case_id=cases[0].id)
    assert exc.value.status_code == 404

    with pytest.raises(HTTPException) as exc:
        _ensure_case_visible(cases[0], admin["student"])
    assert exc.value.status_code == 403

    # 管理员能在病例库看到未发布草稿，才能去完善金标准
    page = CaseBrowseService.list_cases(
        db,
        admin["admin"],
        CaseBrowseQuery(keyword="IDRiD", page=1, page_size=20),
    )
    assert page.total == 5


def test_skip_existing_on_second_run(db, admin, tmp_path):
    src = make_idrid_tree(tmp_path / "idrid", n=2)
    dest = tmp_path / "dest"

    first = run_idrid_import(
        db,
        source_path=str(src),
        dry_run=False,
        creator=admin["admin"],
        dest_root=dest,
    )
    assert first.imported_cases == 2

    second = run_idrid_import(
        db,
        source_path=str(src),
        dry_run=False,
        skip_existing=True,
        creator=admin["admin"],
        dest_root=dest,
    )
    assert second.imported_cases == 0
    assert second.skipped_cases == 2
    assert db.query(TrainingCase).count() == 2


def test_soft_exudate_is_severe_npdr_not_proliferative():
    from app.services.idrid_import_service import grade_from_lesion_counts

    grade, text = grade_from_lesion_counts(
        {"MA": 10, "HE": 100, "EX": 100, "SE": 50},
    )
    assert grade == "3"
    assert "重度" in text
    assert "不能据此诊断增殖期" in text


def test_small_lesions_are_moderate_and_ma_only_is_mild():
    from app.services.idrid_import_service import grade_from_lesion_counts

    moderate, _ = grade_from_lesion_counts({"MA": 10, "HE": 2000, "EX": 2000, "SE": 0})
    large, _ = grade_from_lesion_counts({"HE": 80_000, "SE": 0, "MA": 1})
    mild, _ = grade_from_lesion_counts({"MA": 12})
    assert moderate == "2"
    assert large == "3"
    assert mild == "1"


def test_reviewed_nve_image_is_pdr_without_calling_it_vitreous_hemorrhage():
    from app.services.idrid_import_service import grade_from_lesion_counts

    grade, text = grade_from_lesion_counts(
        {"HE": 1_000_000, "SE": 40_000},
        "IDRiD_17",
    )
    assert grade == "4"
    assert "NVE" in text
    assert "不把本例写成弥漫性玻璃体积血" in text


def _add_case(db, admin, case_no, lesions):
    db.add(TrainingCase(
        case_no=case_no,
        title="旧标题 · DR 4 级",
        description="",
        category="DR",
        difficulty="HARD",
        patient_name="x",
        patient_gender="U",
        patient_phone="",
        clinical_info="增殖性 / 进展期 DR：检出软性渗出",
        gold_dr_grade="4",
        gold_diagnosis="增殖性",
        gold_lesions=lesions,
        teaching_points="",
        is_published=True,
        is_train_case=True,
        creator_id=admin["admin"].id,
    ))


def test_refresh_balances_train_pool_and_keeps_scores(db, admin):
    from app.db.models import PracticeSession
    from app.services.idrid_import_service import refresh_idrid_spectrum

    _add_case(db, admin, "IDRID-T-IDRiD_17", [
        {"type": "HE", "pixel_count": 1_000_000},
        {"type": "SE", "pixel_count": 1000},
    ])
    _add_case(db, admin, "IDRID-T-IDRiD_29", [
        {"type": "HE", "pixel_count": 2000},
        {"type": "EX", "pixel_count": 2000},
        {"type": "MA", "pixel_count": 100},
    ])
    _add_case(db, admin, "IDRID-T-IDRiD_43", [
        {"type": "EX", "pixel_count": 3000},
        {"type": "MA", "pixel_count": 100},
    ])
    _add_case(db, admin, "IDRID-T-IDRiD_35", [
        {"type": "SE", "pixel_count": 8000},
        {"type": "HE", "pixel_count": 200_000},
    ])
    _add_case(db, admin, "IDRID-T-IDRiD_59", [
        {"type": "SE", "pixel_count": 9000},
        {"type": "HE", "pixel_count": 100_000},
    ])
    _add_case(db, admin, "IDRID-T-IDRiD_25", [
        {"type": "SE", "pixel_count": 4000},
        {"type": "HE", "pixel_count": 100_000},
    ])
    _add_case(db, admin, "IDRID-T-IDRiD_33", [
        {"type": "HE", "pixel_count": 200_000},
        {"type": "EX", "pixel_count": 1000},
    ])
    _add_case(db, admin, "IDRID-T-IDRiD_01", [
        {"type": "SE", "pixel_count": 10},
        {"type": "HE", "pixel_count": 10},
    ])
    db.add(TrainingCase(
        case_no="T2026005",
        title="增殖性 DR（PDR，DR 4 级）",
        description="",
        category="DR",
        difficulty="HARD",
        patient_name="x",
        patient_gender="M",
        patient_phone="",
        clinical_info="糖尿病 20 年，视力骤降，玻璃体出血史",
        gold_dr_grade="4",
        gold_diagnosis="增殖性糖尿病视网膜病变，可见视盘新生血管（NVD）",
        gold_lesions=[{"type": "NV", "count": 3}],
        gold_annotations=[{"id": "g1", "tool": "rect", "label": "新生血管", "points": []}],
        teaching_points="PDR",
        is_published=True,
        is_train_case=True,
        creator_id=admin["admin"].id,
    ))
    db.flush()
    case = db.query(TrainingCase).filter(TrainingCase.case_no == "IDRID-T-IDRiD_17").one()
    db.add(PracticeSession(
        user_id=admin["student"].id,
        case_id=case.id,
        mode="RANDOM",
        status="SUBMITTED",
        score_total=88,
        attempt_kind="PRACTICE",
    ))
    db.commit()

    refresh_idrid_spectrum(db)

    kept = db.query(PracticeSession).one()
    assert kept.score_total == 88
    assert kept.status == "SUBMITTED"

    nve = db.query(TrainingCase).filter(TrainingCase.case_no == "IDRID-T-IDRiD_17").one()
    assert nve.gold_dr_grade == "4"
    assert nve.is_train_case is True
    assert "NVE" in nve.gold_diagnosis
    assert "NVE" not in (nve.clinical_info or "")

    cotton = db.query(TrainingCase).filter(TrainingCase.case_no == "IDRID-T-IDRiD_01").one()
    assert cotton.gold_dr_grade == "3"
    assert cotton.is_train_case is False
    assert cotton.gold_diagnosis.startswith("重度 NPDR")

    demo = db.query(TrainingCase).filter(TrainingCase.case_no == "T2026005").one()
    assert demo.gold_dr_grade == "2"
    assert demo.is_train_case is False
    assert demo.is_published is False
    assert demo.gold_annotations == []
    assert "NVD" not in demo.gold_diagnosis


def test_exam_paper_spreads_grades():
    from app.services.practice_service import _pick_across_grades

    class Row:
        def __init__(self, grade):
            self.gold_dr_grade = grade

    cases = [Row("3")] * 8 + [Row("2")] * 2 + [Row("0"), Row("4")]
    picked = _pick_across_grades(cases, 3)
    assert len(picked) == 3
    assert len({row.gold_dr_grade for row in picked}) == 3
