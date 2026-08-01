# -*- coding: utf-8 -*-
"""
状态机

对应《医学培训端评估与工作流重构报告》：
    「阅片与练习的状态流转散落在各处，缺少显式建模与留痕」

原先每个写入点各自 if 一遍当前状态，漏一处就是一个非法跃迁 ——
而且确实漏了一处，见 test_teacher_cannot_approve_a_draft。
"""

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.common import workflow
from app.db.base import Base
from app.db.models import (
    ReadingAnnotation,
    ReadingStatusEnum,
    Role,
    RoleEnum,
    TrainingCase,
    User,
)
from app.db.models.operation_log import OperationLog
from app.schemas.reading import ReadingReviewParams, ReadingSaveParams
from app.services.reading_service import ReadingService


# --------------------------------------------------------------------------
# 流转表本身
# --------------------------------------------------------------------------

def test_reading_normal_path():
    wf = workflow.READING
    assert wf.can("DRAFT", "SUBMITTED")
    assert wf.can("SUBMITTED", "REVIEWED")
    assert wf.can("SUBMITTED", "REJECTED")
    assert wf.can("REJECTED", "SUBMITTED")


def test_reading_cannot_skip_submission():
    """草稿不能直接变成已通过 —— 那等于跳过学员提交这一环"""
    assert not workflow.READING.can("DRAFT", "REVIEWED")


def test_reviewed_is_terminal():
    """
    已通过的结论不能就地改。要改只能重新阅片 ——
    否则审核过的结论被悄悄改掉，审核就失去意义了。
    """
    for target in ("DRAFT", "SUBMITTED", "REJECTED", "REVIEWED"):
        assert not workflow.READING.can("REVIEWED", target)


def test_practice_has_no_rejection():
    """练习提交即评分，成绩已产生，退回去改没有意义"""
    assert "REJECTED" not in workflow.PRACTICE.transitions.get("SUBMITTED", set())


def test_practice_review_can_be_amended():
    """教师改措辞、补充意见是正常操作"""
    assert workflow.PRACTICE.can("REVIEWED", "REVIEWED")


def test_practice_cannot_be_resubmitted():
    assert not workflow.PRACTICE.can("SUBMITTED", "SUBMITTED")


def test_illegal_transition_raises_409_with_readable_states():
    """
    409 而不是 400：请求本身没写错，是实体当前状态不允许这个动作。
    提示里要出现中文状态名，不能让用户看见 DRAFT / REVIEWED。
    """
    with pytest.raises(HTTPException) as exc:
        workflow.READING.ensure("DRAFT", "REVIEWED")
    assert exc.value.status_code == 409
    assert "草稿" in exc.value.detail
    assert "已通过" in exc.value.detail


def test_unknown_state_is_not_silently_allowed():
    """脏数据里出现没见过的状态时，应当拦住而不是放行"""
    with pytest.raises(HTTPException):
        workflow.READING.ensure("WHATEVER", "REVIEWED")


# --------------------------------------------------------------------------
# 接入业务后的实际效果
# --------------------------------------------------------------------------

@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def ctx(db):
    srole = Role(code=RoleEnum.STUDENT.value, name="学员")
    trole = Role(code=RoleEnum.TEACHER.value, name="教师")
    db.add_all([srole, trole])
    db.flush()
    student = User(username="stu", password_hash="x", role_id=srole.id)
    teacher = User(username="tea", password_hash="x", role_id=trole.id)
    db.add_all([student, teacher])
    db.flush()
    case = TrainingCase(case_no="W-001", title="流转", category="DR",
                        gold_dr_grade="2", is_published=1, is_train_case=1,
                        creator_id=teacher.id)
    db.add(case)
    db.commit()
    return student, teacher, case


def _save(case_id, submit, request_id=""):
    return ReadingSaveParams(
        case_id=case_id,
        image_index=0,
        image_url="/static/a.jpg",
        diagnosis={
            "readability": "readable",
            "dr_grade": "2",
            "confidence": "high",
            "disposition": "followup_6m",
        },
        submit=submit,
        request_id=request_id,
    )


def test_teacher_cannot_approve_a_draft(db, ctx):
    """
    这是接入状态机之前真实存在的漏洞：审核只在「驳回」分支校验了状态，
    「通过」分支没校验，教师能直接通过一份从未提交的草稿。
    """
    student, teacher, case = ctx
    ReadingService.save(db, student, _save(case.id, submit=False))
    row = db.query(ReadingAnnotation).first()
    assert row.status == ReadingStatusEnum.DRAFT.value

    with pytest.raises(HTTPException) as exc:
        ReadingService.review(db, teacher, row.id,
                              ReadingReviewParams(review_comment="不错", accept=True))
    assert exc.value.status_code == 409


def test_rejection_does_not_rewind_to_draft(db, ctx):
    """
    驳回落到 REJECTED。倒回 DRAFT 会抹掉「从未提交」和
    「提交过但被驳回」的区别，教师的待办列表就分不出来了。
    """
    student, teacher, case = ctx
    ReadingService.save(db, student, _save(case.id, submit=True, request_id="r1"))
    row = db.query(ReadingAnnotation).first()

    out = ReadingService.review(db, teacher, row.id,
                                ReadingReviewParams(review_comment="征象漏了", accept=False))
    assert out.status == ReadingStatusEnum.REJECTED.value


def test_rejected_record_is_revised_in_place(db, ctx):
    """
    驳回的意义是让学员改完再交。若不复用原记录，
    学员一改就变成新的一条，教师看不出这是上次那份的修订。
    """
    student, teacher, case = ctx
    ReadingService.save(db, student, _save(case.id, submit=True, request_id="r1"))
    row = db.query(ReadingAnnotation).first()
    ReadingService.review(db, teacher, row.id,
                          ReadingReviewParams(review_comment="改", accept=False))

    ReadingService.save(db, student, _save(case.id, submit=False))
    assert db.query(ReadingAnnotation).count() == 1

    out = ReadingService.save(db, student, _save(case.id, submit=True, request_id="r2"))
    assert out.id == row.id
    assert out.status == ReadingStatusEnum.SUBMITTED.value


def test_approved_reading_cannot_be_resubmitted(db, ctx):
    """已通过的记录不该被学员再改一遍交上来"""
    student, teacher, case = ctx
    ReadingService.save(db, student, _save(case.id, submit=True, request_id="r1"))
    row = db.query(ReadingAnnotation).first()
    ReadingService.review(db, teacher, row.id,
                          ReadingReviewParams(review_comment="通过", accept=True))

    # 已通过的记录不再被复用，学员再阅片是新的一份，不影响已通过那条
    out = ReadingService.save(db, student, _save(case.id, submit=True, request_id="r2"))
    assert out.id != row.id
    db.refresh(row)
    assert row.status == ReadingStatusEnum.REVIEWED.value


def test_every_transition_is_audited(db, ctx):
    """状态流转要能看出从哪来、到哪去，只写「已提交」是不够的"""
    student, teacher, case = ctx
    ReadingService.save(db, student, _save(case.id, submit=True, request_id="r1"))
    row = db.query(ReadingAnnotation).first()
    ReadingService.review(db, teacher, row.id,
                          ReadingReviewParams(review_comment="改", accept=False))

    logs = db.query(OperationLog).filter(OperationLog.module == "reading").all()
    details = " | ".join(log.detail for log in logs)
    assert "草稿 → 待审核" in details
    assert "待审核 → 已驳回" in details
