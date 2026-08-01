# -*- coding: utf-8 -*-
"""
练习提交的幂等与审计

对应《医学培训端评估与工作流重构报告》8.3 P1 用例：
    「保存时断网并重复点击 → 不丢失、不重复提交」

这里用真实的 SQLite 会话，不打桩 —— 幂等靠的是数据库的
「WHERE status='DRAFT'」条件更新，打桩测出来的是假的。
"""

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import (
    PracticeSession,
    PracticeStatusEnum,
    Role,
    RoleEnum,
    TrainingCase,
    User,
)
from app.db.models.operation_log import OperationLog
from app.schemas.practice import PracticeSubmitParams
from app.services.practice_service import PracticeService


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
def student(db):
    role = Role(code=RoleEnum.STUDENT.value, name="学员")
    db.add(role)
    db.flush()
    user = User(username="stu001", password_hash="x", real_name="学员甲", role_id=role.id)
    db.add(user)
    db.commit()
    return user


@pytest.fixture()
def session_row(db, student):
    case = TrainingCase(
        case_no="T-001",
        title="测试病例",
        category="DR",
        gold_dr_grade="2",
        is_published=1,
        is_train_case=1,
        creator_id=student.id,
    )
    db.add(case)
    db.flush()
    row = PracticeSession(
        user_id=student.id,
        case_id=case.id,
        status=PracticeStatusEnum.DRAFT.value,
    )
    db.add(row)
    db.commit()
    return row


def _params(session_id, request_id="", grade="2"):
    return PracticeSubmitParams(
        session_id=session_id,
        student_dr_grade=grade,
        student_diagnosis="中度非增殖期病变",
        request_id=request_id,
    )


# --------------------------------------------------------------------------
# 断网重试
# --------------------------------------------------------------------------

def test_retry_with_same_key_returns_original_result(db, student, session_row):
    """
    提交成功但响应丢包，学员重试 —— 必须拿回原成绩，不能报错。
    报错会让学员以为答卷丢了，而实际上早就判完分了。
    """
    first = PracticeService.submit(db, student, _params(session_row.id, "req-abc"))
    again = PracticeService.submit(db, student, _params(session_row.id, "req-abc"))

    assert again.id == first.id
    assert again.score_total == first.score_total
    assert again.status == "SUBMITTED"


def test_retry_does_not_create_a_second_record(db, student, session_row):
    PracticeService.submit(db, student, _params(session_row.id, "req-abc"))
    PracticeService.submit(db, student, _params(session_row.id, "req-abc"))

    assert db.query(PracticeSession).count() == 1


def test_retry_does_not_rescore(db, student, session_row):
    """
    重试是回放，不是重判。若第二次带着不同答案重来还照判，
    等于给了一次免费改答案的机会。
    """
    first = PracticeService.submit(db, student, _params(session_row.id, "req-abc", grade="0"))
    again = PracticeService.submit(db, student, _params(session_row.id, "req-abc", grade="2"))

    assert again.student_dr_grade == first.student_dr_grade == "0"
    assert again.score_total == first.score_total


# --------------------------------------------------------------------------
# 真正的重复提交
# --------------------------------------------------------------------------

def test_different_key_is_a_real_duplicate_and_rejected(db, student, session_row):
    """
    另开一个标签页再答一遍 —— 成绩已经产生，不允许覆盖。
    """
    PracticeService.submit(db, student, _params(session_row.id, "req-abc"))
    with pytest.raises(HTTPException) as exc:
        PracticeService.submit(db, student, _params(session_row.id, "req-xyz"))
    # 409 而不是 400：请求本身没写错，是会话状态不允许再次提交
    assert exc.value.status_code == 409


def test_no_key_falls_back_to_rejecting(db, student, session_row):
    """
    旧客户端不带幂等键：无法区分重试和重复提交，
    只能保守地拒绝 —— 宁可让学员看到一次错误提示，
    也不能把已有成绩冲掉。
    """
    PracticeService.submit(db, student, _params(session_row.id))
    with pytest.raises(HTTPException):
        PracticeService.submit(db, student, _params(session_row.id))


def test_empty_key_does_not_match_stored_empty_key(db, student, session_row):
    """
    空键不能当成「匹配上了」—— 否则任何不带键的请求
    都会被当作前一次的重试。
    """
    PracticeService.submit(db, student, _params(session_row.id, ""))
    row = db.query(PracticeSession).first()
    assert row.submit_request_id is None

    with pytest.raises(HTTPException):
        PracticeService.submit(db, student, _params(session_row.id, ""))


# --------------------------------------------------------------------------
# 双击：两个请求同时在途
# --------------------------------------------------------------------------

def _two_connections(tmp_path):
    """
    独立两条连接的真数据库。共享内存库只有一条连接，
    测不出并发 —— 而并发正是条件更新要防的东西。
    """
    engine = create_engine(f"sqlite:///{tmp_path}/t.db")
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine)
    return maker(), maker()


def test_double_click_only_scores_once(tmp_path):
    """
    两个请求都读到了 DRAFT（谁都没看见对方），
    条件更新让数据库来裁决只有一个能落库。
    """
    a, b = _two_connections(tmp_path)
    role = Role(code=RoleEnum.STUDENT.value, name="学员")
    a.add(role)
    a.flush()
    user = User(username="stu001", password_hash="x", role_id=role.id)
    a.add(user)
    a.flush()
    case = TrainingCase(case_no="T-002", title="并发", category="DR",
                        gold_dr_grade="2", is_published=1, is_train_case=1,
                        creator_id=user.id)
    a.add(case)
    a.flush()
    a.add(PracticeSession(user_id=user.id, case_id=case.id,
                          status=PracticeStatusEnum.DRAFT.value))
    a.commit()

    sid = a.query(PracticeSession).first().id
    user_a = a.query(User).first()
    user_b = b.query(User).first()

    # 两边各自把会话读进内存，此时都还是 DRAFT。
    # 必须用变量持住：SQLAlchemy 的 identity map 是弱引用，
    # 不持引用的话对象会被回收，b 后面重查就拿到新状态，
    # 竞态就复现不出来了 —— 测试会因为错误的原因通过。
    stale_a = a.query(PracticeSession).filter(PracticeSession.id == sid).first()
    stale_b = b.query(PracticeSession).filter(PracticeSession.id == sid).first()
    assert stale_a.status == stale_b.status == PracticeStatusEnum.DRAFT.value

    first = PracticeService.submit(a, user_a, _params(sid, "req-1", grade="0"))

    # b 手里仍是 DRAFT，会一路走到条件更新那步
    assert stale_b.status == PracticeStatusEnum.DRAFT.value
    with pytest.raises(HTTPException):
        PracticeService.submit(b, user_b, _params(sid, "req-2", grade="4"))

    b.expire_all()
    row = b.query(PracticeSession).filter(PracticeSession.id == sid).first()
    assert row.student_dr_grade == "0", "后到的请求覆盖了先到的成绩"
    assert row.score_total == first.score_total
    a.close()
    b.close()


# --------------------------------------------------------------------------
# 审计
# --------------------------------------------------------------------------

def test_submit_is_audited(db, student, session_row):
    """成绩有争议时要能回溯：谁、何时、按哪套口径判了多少分"""
    PracticeService.submit(db, student, _params(session_row.id, "req-abc"))

    logs = db.query(OperationLog).filter(OperationLog.action == "submit").all()
    assert len(logs) == 1
    assert logs[0].user_id == student.id
    assert str(session_row.id) in logs[0].detail
    assert "口径" in logs[0].detail


def test_retry_does_not_double_log(db, student, session_row):
    """重试是回放，不该再记一条审计 —— 否则台账里凭空多出一次提交"""
    PracticeService.submit(db, student, _params(session_row.id, "req-abc"))
    PracticeService.submit(db, student, _params(session_row.id, "req-abc"))

    logs = db.query(OperationLog).filter(OperationLog.action == "submit").all()
    assert len(logs) == 1
