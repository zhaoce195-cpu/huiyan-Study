# -*- coding: utf-8 -*-
"""同一病人可以有多次检查。公共数据集没提供编号和日期时，仍是一行一张图。"""

from app.db.models import TrainingCase
from app.schemas.case_browse import CaseBrowseQuery, SubjectLinkUpdate
from app.services.case_browse_service import CaseBrowseService
from app.services.case_import_service import CaseImportService
from tests.test_case_import import _db, _png, _user
from app.db.models.user import RoleEnum


def _case(db, teacher, case_no, subject="", exam=""):
    row = TrainingCase(
        case_no=case_no,
        title=case_no,
        description="",
        category="DR",
        difficulty="EASY",
        patient_name="",
        patient_gender="U",
        patient_phone="",
        subject_no=subject,
        exam_on=exam,
        clinical_info="",
        image_paths={"OD": ["x"]},
        gold_dr_grade="2",
        gold_diagnosis="",
        teaching_points="",
        is_published=True,
        is_train_case=True,
        creator_id=teacher.id,
    )
    db.add(row)
    db.commit()
    return row


def test_blank_subject_stays_one_image_and_dated_visits_order():
    db = _db()
    teacher = _user(db, RoleEnum.TEACHER.value)
    single = _case(db, teacher, "IDRID-1")
    later = _case(db, teacher, "T-LATER", "P-01", "2024-09-01")
    earlier = _case(db, teacher, "T-EARLIER", "P-01", "2024-03-01")
    page = CaseBrowseService.list_cases(db, teacher, CaseBrowseQuery(page=1, page_size=20))
    by_no = {item.case_no: item for item in page.list}
    assert by_no[single.case_no].visit_count == 1
    assert by_no[single.case_no].exam_on == ""
    assert by_no[earlier.case_no].visit_index == 1
    assert by_no[later.case_no].visit_index == 2
    assert by_no[later.case_no].visit_count == 2
    detail = CaseBrowseService.get_detail(db, teacher, later.id)
    assert [item.case_no for item in detail.visits] == ["T-EARLIER"]
    assert detail.visits[0].exam_on == "2024-03-01"
    from app.services.reading_service import ReadingService
    opened = ReadingService.get_image_source(db, teacher, later.id)
    assert opened.exam_on == "2024-09-01"
    assert opened.exam_date_known is True
    assert opened.visit_index == 2
    assert opened.visit_count == 2
    assert opened.visits[0]["caseNo"] == "T-EARLIER"
    assert opened.visits[0]["examOn"] == "2024-03-01"
    alone = ReadingService.get_image_source(db, teacher, single.id)
    assert alone.exam_on == ""
    assert alone.exam_date_known is False
    assert alone.visit_count == 1
    db.close()


def test_import_links_two_dates_and_rejects_a_made_up_date():
    db = _db()
    teacher = _user(db, RoleEnum.TEACHER.value)
    head = "登记号,标题,病种,难度,年龄,性别,眼别,临床信息,病人编号,检查日期\n"
    ok = CaseImportService.check(
        db,
        teacher,
        (
            head
            + "A001,第一次,糖尿病视网膜病变,入门,60,女,右眼,病史,P-01,2024-03-01\n"
            + "A002,第二次,糖尿病视网膜病变,入门,60,女,右眼,病史,P-01,2024-09-01\n"
        ).encode("utf-8"),
        [
            ("A001_右眼.png", _png(480, (20, 40, 60))),
            ("A002_右眼.png", _png(480, (60, 40, 20))),
        ],
    )
    assert ok["passed"] == 2
    created = CaseImportService.commit(db, teacher, ok["token"])
    rows = db.query(TrainingCase).filter(TrainingCase.subject_no == "P-01").all()
    assert {row.exam_on for row in rows} == {"2024-03-01", "2024-09-01"}
    assert len(created["created"]) == 2

    bad = CaseImportService.check(
        db,
        teacher,
        (head + "A003,日期不对,正常,入门,40,男,右眼,病史,P-02,去年\n").encode("utf-8"),
        [("A003_右眼.png", _png(480, (10, 80, 10)))],
    )
    assert bad["passed"] == 0
    assert any("不要编造" in item for item in bad["rows"][0]["issues"])

    linked = CaseBrowseService.set_subject(
        db, teacher, rows[0].id, SubjectLinkUpdate(subject_no="P-09", exam_on=""),
    )
    assert linked.subject_no == "P-09"
    assert linked.exam_on == ""
    from app.common.utils import screening_dir
    for case in db.query(TrainingCase).all():
        paths = case.image_paths or {}
        for urls in paths.values():
            for url in urls or []:
                (screening_dir() / str(url).rsplit("/", 1)[-1]).unlink(missing_ok=True)
    db.close()
