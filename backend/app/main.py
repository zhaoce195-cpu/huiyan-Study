"""
应用入口
- 创建 FastAPI 实例
- 全局跨域 / 静态文件 / 异常处理 / 路由注册
- 启动钩子：自动建表 + 角色 / 管理员账号初始化
"""

import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_v1_router
from app.common.response import (
    CODE_INTERNAL,
    CODE_UNAUTHORIZED,
    CODE_VALIDATION,
)
from app.core.config import settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.models import Role, RoleEnum, User, UserSetting
from app.db.session import SessionLocal, engine


# ============================================================
#                   启动 / 关闭钩子
# ============================================================

def _patch_schema() -> None:
    """
    线上环境兼容补丁：当 ORM 增加新字段、而旧库尚未迁移时，
    自动 ALTER TABLE 补齐，避免报「Unknown column」。

    仅做幂等的 ADD COLUMN，不做任何破坏性改动。
    """
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    try:
        cols = {c["name"] for c in insp.get_columns("biz_training_case")}
    except Exception:
        cols = set()
    try:
        sc_cols = {c["name"] for c in insp.get_columns("biz_screening_case")}
    except Exception:
        sc_cols = set()
    try:
        user_cols = {c["name"] for c in insp.get_columns("sys_user")}
    except Exception:
        user_cols = set()

    is_sqlite = engine.url.drivername.startswith("sqlite")

    patches: list[tuple[str, str]] = []

    # ---- sys_user：微信小程序登录 openid ----
    if user_cols and "wx_openid" not in user_cols:
        patches.append((
            "sys_user.wx_openid",
            "ALTER TABLE sys_user ADD COLUMN wx_openid "
            "VARCHAR(64) NOT NULL DEFAULT ''",
        ))

    if cols and "archive_status" not in cols:
        patches.append((
            "biz_training_case.archive_status",
            "ALTER TABLE biz_training_case ADD COLUMN archive_status "
            "VARCHAR(16) NOT NULL DEFAULT 'ACTIVE'",
        ))
    if cols and "is_train_case" not in cols:
        # SQLite/MySQL 都支持 BOOLEAN 关键字（MySQL 内部为 TINYINT(1)）
        patches.append((
            "biz_training_case.is_train_case",
            "ALTER TABLE biz_training_case ADD COLUMN is_train_case "
            "BOOLEAN NOT NULL DEFAULT 0",
        ))

    # ---- biz_screening_case：体检报告确认相关字段 ----
    if sc_cols and "report_status" not in sc_cols:
        patches.append((
            "biz_screening_case.report_status",
            "ALTER TABLE biz_screening_case ADD COLUMN report_status "
            "VARCHAR(16) NOT NULL DEFAULT 'pending'",
        ))
    if sc_cols and "report_pdf_path" not in sc_cols:
        patches.append((
            "biz_screening_case.report_pdf_path",
            "ALTER TABLE biz_screening_case ADD COLUMN report_pdf_path "
            "VARCHAR(512) NOT NULL DEFAULT ''",
        ))
    if sc_cols and "patient_user_id" not in sc_cols:
        # ondelete=SET NULL 在 SQLite 默认不强制，但 MySQL 会按 FK 行为
        patches.append((
            "biz_screening_case.patient_user_id",
            "ALTER TABLE biz_screening_case ADD COLUMN patient_user_id "
            "INTEGER NULL",
        ))

    # ---- 全局唯一编号 case_sn（双表）----
    if sc_cols and "case_sn" not in sc_cols:
        patches.append((
            "biz_screening_case.case_sn",
            "ALTER TABLE biz_screening_case ADD COLUMN case_sn VARCHAR(32) NULL",
        ))
    if cols and "case_sn" not in cols:
        patches.append((
            "biz_training_case.case_sn",
            "ALTER TABLE biz_training_case ADD COLUMN case_sn VARCHAR(32) NULL",
        ))

    # ---- 实训病例：模拟患者信息 ----
    if cols and "patient_name" not in cols:
        patches.append((
            "biz_training_case.patient_name",
            "ALTER TABLE biz_training_case ADD COLUMN patient_name "
            "VARCHAR(64) NOT NULL DEFAULT ''",
        ))
    if cols and "patient_phone" not in cols:
        patches.append((
            "biz_training_case.patient_phone",
            "ALTER TABLE biz_training_case ADD COLUMN patient_phone "
            "VARCHAR(20) NOT NULL DEFAULT ''",
        ))

    if not patches:
        return

    with engine.begin() as conn:
        for name, sql in patches:
            try:
                conn.execute(text(sql))
                print(f"[schema_patch] + 已补齐 {name}")
            except Exception as e:  # noqa: BLE001
                print(f"[schema_patch] x 补齐 {name} 失败：{e}")
                if is_sqlite:
                    raise


def _init_database() -> None:
    """开发环境自动建表 + 默认数据"""
    Base.metadata.create_all(bind=engine)
    _patch_schema()

    db = SessionLocal()
    try:
        # 1. 角色初始化
        defaults = [
            (RoleEnum.STUDENT.value, "学员", "学员用户：仅学习和阅片练习权限"),
            (RoleEnum.TEACHER.value, "带教老师", "教学带教用户：负责课程与考核"),
            (RoleEnum.ADMIN.value, "管理员", "管理员用户：拥有系统全部权限"),
        ]
        existing = {r.code: r for r in db.query(Role).all()}
        for code, name, remark in defaults:
            if code not in existing:
                db.add(Role(code=code, name=name, remark=remark))
        db.commit()

        # 2. 默认管理员账号
        admin_role = db.query(Role).filter(Role.code == RoleEnum.ADMIN.value).first()
        if admin_role and not db.query(User).filter(User.username == "admin").first():
            admin = User(
                username="admin",
                password_hash=hash_password("Admin@123"),
                real_name="系统管理员",
                role_id=admin_role.id,
                department="信息中心",
                title="系统管理员",
                email="admin@huiyan.local",
                is_active=True,
            )
            admin.setting = UserSetting(user_id=0)
            db.add(admin)
            db.commit()

        # 3. 演示账号（教师 / 学员）
        for username, role_code, real_name, dept, title in (
            ("teacher", RoleEnum.TEACHER.value, "李老师", "眼科", "副主任医师"),
            ("student", RoleEnum.STUDENT.value, "张同学", "眼科", "住培医师"),
        ):
            if not db.query(User).filter(User.username == username).first():
                role = db.query(Role).filter(Role.code == role_code).first()
                if not role:
                    continue
                u = User(
                    username=username,
                    password_hash=hash_password("Huiyan@123"),
                    real_name=real_name,
                    role_id=role.id,
                    department=dept,
                    title=title,
                    is_active=True,
                )
                u.setting = UserSetting(user_id=0)
                db.add(u)
        db.commit()
    except Exception as e:
        db.rollback()
        # 建表/初始化失败不阻塞应用启动，只打印告警
        print(f"[init_database] 警告：{e}")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    if settings.DEBUG:
        try:
            _init_database()
        except SQLAlchemyError as e:
            print(f"[startup] 数据库初始化失败（请确认 MySQL 已启动且配置正确）：{e}")
    yield


# ============================================================
#                       FastAPI 实例
# ============================================================

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description="""
**慧眼教学云后端服务** · 账号身份登录 + 个人中心

- 接口前缀：`/api/v1`
- 认证方式：`Authorization: Bearer <token>`
- 统一响应：`{ code, msg, data }`，业务码 `0` 为成功
""",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# ============================================================
#                       全局中间件
# ============================================================

# 跨域：开发环境允许所有源；生产建议精确配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """简单的耗时统计 + 异常兜底"""
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as e:
        # 兜底：避免任何未捕获异常导致进程崩溃
        return JSONResponse(
            status_code=200,
            content={
                "code": CODE_INTERNAL,
                "msg": f"服务器内部错误：{e}",
                "data": None,
            },
        )
    response.headers["X-Process-Time"] = f"{(time.perf_counter() - start) * 1000:.2f}ms"
    return response


# ============================================================
#                       全局异常
# ============================================================

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_request: Request, exc: StarletteHTTPException):
    """统一 HTTPException 响应结构"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code,
            "msg": exc.detail if isinstance(exc.detail, str) else "请求失败",
            "data": None,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError):
    """Pydantic 校验异常 → 422 友好提示"""
    errors = exc.errors()
    first = errors[0] if errors else {}
    field = ".".join(str(x) for x in first.get("loc", []))
    msg = first.get("msg", "参数校验失败")
    return JSONResponse(
        status_code=200,
        content={
            "code": CODE_VALIDATION,
            "msg": f"{field}: {msg}" if field else msg,
            "data": jsonable_encoder(errors),
        },
    )


@app.exception_handler(SQLAlchemyError)
async def db_exception_handler(_request: Request, exc: SQLAlchemyError):
    return JSONResponse(
        status_code=200,
        content={
            "code": CODE_INTERNAL,
            "msg": "数据库异常，请稍后再试",
            "data": str(exc) if settings.DEBUG else None,
        },
    )


# ============================================================
#                  静态资源（头像访问入口）
# ============================================================
static_root = Path(settings.UPLOAD_DIR)
static_root.mkdir(parents=True, exist_ok=True)
app.mount(settings.STATIC_URL, StaticFiles(directory=static_root), name="static")


# ============================================================
#                       路由注册
# ============================================================

@app.get("/", include_in_schema=False)
def root():
    return {
        "code": 0,
        "msg": "ok",
        "data": {
            "name": settings.PROJECT_NAME,
            "version": settings.PROJECT_VERSION,
            "docs": "/docs",
            "redoc": "/redoc",
            "api": settings.API_V1_PREFIX,
        },
    }


@app.get("/health", include_in_schema=False)
def health():
    """健康检查 — 不依赖数据库，用于负载均衡探活"""
    return {"code": 0, "msg": "ok", "data": {"status": "ok"}}


# 业务路由统一挂到 /api/v1
app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)


# 让 401 走我们的统一格式
@app.exception_handler(401)
async def unauthorized_handler(_request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=401,
        content={
            "code": CODE_UNAUTHORIZED,
            "msg": exc.detail if isinstance(exc.detail, str) else "未登录或登录已失效",
            "data": None,
        },
    )
