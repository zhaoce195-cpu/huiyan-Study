# -*- coding: utf-8 -*-
"""
管理员 · 用户账号
新建 / 重置密码（下次必改） / 停用后不能登录
"""

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import Role, RoleEnum, User
from app.schemas.user import (
    AdminSetActiveParams,
    AdminUserCreate,
    ChangePasswordRequest,
    LoginRequest,
)
from app.services.admin_user_service import AdminUserService
from app.services.auth_service import AuthService
from app.services.user_service import UserService


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
def seeded(db):
    from app.core.security import hash_password

    roles = {
        RoleEnum.ADMIN.value: Role(code=RoleEnum.ADMIN.value, name="管理员"),
        RoleEnum.TEACHER.value: Role(code=RoleEnum.TEACHER.value, name="教师"),
        RoleEnum.STUDENT.value: Role(code=RoleEnum.STUDENT.value, name="学员"),
    }
    db.add_all(list(roles.values()))
    db.flush()

    admin = User(
        username="admin",
        password_hash=hash_password("Admin@123"),
        real_name="系统管理员",
        role_id=roles[RoleEnum.ADMIN.value].id,
        is_active=True,
    )
    teacher = User(
        username="teacher",
        password_hash=hash_password("Huiyan@123"),
        real_name="李老师",
        role_id=roles[RoleEnum.TEACHER.value].id,
        is_active=True,
    )
    db.add_all([admin, teacher])
    db.commit()
    db.refresh(admin)
    db.refresh(teacher)
    return {"admin": admin, "teacher": teacher}


def test_create_student_and_login(db, seeded):
    item = AdminUserService.create_user(
        db,
        operator=seeded["admin"],
        params=AdminUserCreate(
            username="stu01",
            real_name="新学员",
            role=RoleEnum.STUDENT,
            department="眼科",
            password="Init@123",
        ),
    )
    assert item.username == "stu01"
    assert item.role == RoleEnum.STUDENT.value
    assert item.is_active is True
    assert item.must_change_password is True

    login = AuthService.login(db, LoginRequest(username="stu01", password="Init@123"))
    assert login.user_info.username == "stu01"
    assert login.user_info.must_change_password is True


def test_disable_blocks_login(db, seeded):
    item = AdminUserService.create_user(
        db,
        operator=seeded["admin"],
        params=AdminUserCreate(
            username="stu02",
            real_name="待停用",
            role=RoleEnum.STUDENT,
            password="Init@123",
        ),
    )
    AdminUserService.set_active(
        db,
        operator=seeded["admin"],
        user_id=item.id,
        params=AdminSetActiveParams(is_active=False),
    )
    with pytest.raises(HTTPException) as exc:
        AuthService.login(db, LoginRequest(username="stu02", password="Init@123"))
    assert exc.value.status_code == 403
    assert "停用" in str(exc.value.detail)

    AdminUserService.set_active(
        db,
        operator=seeded["admin"],
        user_id=item.id,
        params=AdminSetActiveParams(is_active=True),
    )
    login = AuthService.login(db, LoginRequest(username="stu02", password="Init@123"))
    assert login.user_info.is_active is True


def test_reset_password_requires_change(db, seeded):
    item = AdminUserService.create_user(
        db,
        operator=seeded["admin"],
        params=AdminUserCreate(
            username="stu03",
            real_name="重置",
            role=RoleEnum.TEACHER,
            password="Init@123",
        ),
    )
    out = AdminUserService.reset_password(
        db, operator=seeded["admin"], user_id=item.id,
    )
    assert out.temp_password
    assert out.must_change_password is True

    with pytest.raises(HTTPException):
        AuthService.login(db, LoginRequest(username="stu03", password="Init@123"))

    login = AuthService.login(
        db, LoginRequest(username="stu03", password=out.temp_password),
    )
    assert login.user_info.must_change_password is True

    user = db.query(User).filter(User.id == item.id).one()
    UserService.change_password(
        db,
        user=user,
        params=ChangePasswordRequest(
            old_password=out.temp_password,
            new_password="NewPass@1",
            confirm_password="NewPass@1",
        ),
    )
    db.refresh(user)
    assert user.must_change_password is False


def test_cannot_disable_self(db, seeded):
    with pytest.raises(HTTPException) as exc:
        AdminUserService.set_active(
            db,
            operator=seeded["admin"],
            user_id=seeded["admin"].id,
            params=AdminSetActiveParams(is_active=False),
        )
    assert exc.value.status_code == 400


def test_cannot_disable_last_admin(db, seeded):
    other = AdminUserService.create_user(
        db,
        operator=seeded["admin"],
        params=AdminUserCreate(
            username="admin2",
            real_name="第二管理",
            role=RoleEnum.ADMIN,
            password="Admin@456",
        ),
    )
    # 先停用后来的这个，只剩最初的 admin
    AdminUserService.set_active(
        db,
        operator=seeded["admin"],
        user_id=other.id,
        params=AdminSetActiveParams(is_active=False),
    )
    # 用另一个会话对象模拟「别人停用最后一名」——这里用 teacher 当 operator 只测计数
    # 真正拦的是「排除自己后没有其他启用管理员」
    # 再造一个管理员来停用最初的 admin：此时 admin2 已停用，应被拒绝
    with pytest.raises(HTTPException) as exc:
        AdminUserService.set_active(
            db,
            operator=seeded["teacher"],
            user_id=seeded["admin"].id,
            params=AdminSetActiveParams(is_active=False),
        )
    assert exc.value.status_code == 400
    assert "管理员" in str(exc.value.detail)


def test_duplicate_username(db, seeded):
    with pytest.raises(HTTPException) as exc:
        AdminUserService.create_user(
            db,
            operator=seeded["admin"],
            params=AdminUserCreate(
                username="teacher",
                real_name="重名",
                role=RoleEnum.STUDENT,
                password="Init@123",
            ),
        )
    assert exc.value.status_code == 400


def test_list_filters_role(db, seeded):
    AdminUserService.create_user(
        db,
        operator=seeded["admin"],
        params=AdminUserCreate(
            username="stu04",
            real_name="筛选用",
            role=RoleEnum.STUDENT,
            password="Init@123",
        ),
    )
    page = AdminUserService.list_users(db, role=RoleEnum.STUDENT.value)
    assert page.total >= 1
    assert all(it.role == RoleEnum.STUDENT.value for it in page.list)
