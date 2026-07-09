"""
数据库初始化脚本（独立工具，不会随应用启动）
功能：
    - 自动建表（基于 SQLAlchemy 模型）
    - 写入三个默认角色
    - 写入三个演示账号：admin / teacher / student

用法：
    python init_data.py
"""

from datetime import datetime

from app.core.security import hash_password
from app.db.base import Base
from app.db.models import Role, RoleEnum, User, UserSetting
from app.db.session import SessionLocal, engine


DEFAULT_ROLES = [
    (RoleEnum.STUDENT.value, "学员", "学员用户：仅学习和阅片练习权限"),
    (RoleEnum.TEACHER.value, "带教老师", "教学带教用户：负责课程与考核"),
    (RoleEnum.ADMIN.value, "管理员", "管理员用户：拥有系统全部权限"),
]

DEFAULT_USERS = [
    # username, password, role_code, real_name, dept, title, email
    ("admin",   "Admin@123",  RoleEnum.ADMIN.value,   "系统管理员", "信息中心", "系统管理员", "admin@huiyan.local"),
    ("teacher", "Huiyan@123", RoleEnum.TEACHER.value, "李老师",   "眼科",   "副主任医师", "li.teacher@huiyan.local"),
    ("student", "Huiyan@123", RoleEnum.STUDENT.value, "张同学",   "眼科",   "住培医师",   "student@huiyan.local"),
]


def main() -> None:
    print(f"[{datetime.now()}] 1. 创建表结构 …")
    Base.metadata.create_all(bind=engine)
    print("    ✔ 表结构已就绪")

    db = SessionLocal()
    try:
        # 角色
        print(f"[{datetime.now()}] 2. 写入默认角色 …")
        existing_codes = {r.code for r in db.query(Role).all()}
        for code, name, remark in DEFAULT_ROLES:
            if code not in existing_codes:
                db.add(Role(code=code, name=name, remark=remark))
                print(f"    + {code} - {name}")
        db.commit()

        # 用户
        print(f"[{datetime.now()}] 3. 写入演示账号 …")
        for username, password, role_code, real_name, dept, title, email in DEFAULT_USERS:
            if db.query(User).filter(User.username == username).first():
                print(f"    ⓘ {username} 已存在，跳过")
                continue
            role = db.query(Role).filter(Role.code == role_code).first()
            if not role:
                print(f"    ✘ 找不到角色 {role_code}")
                continue
            user = User(
                username=username,
                password_hash=hash_password(password),
                real_name=real_name,
                role_id=role.id,
                department=dept,
                title=title,
                email=email,
                is_active=True,
            )
            user.setting = UserSetting(user_id=0)
            db.add(user)
            print(f"    + {username} / {password}  (role={role_code})")
        db.commit()

        print(f"[{datetime.now()}] ✅ 初始化完成")
        print("\n  默认登录账号：")
        for u, p, r, *_ in DEFAULT_USERS:
            print(f"    - {u} / {p}  ({r})")
    except Exception as e:
        db.rollback()
        print(f"❌ 初始化失败：{e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
