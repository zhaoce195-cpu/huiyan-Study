"""
数据库会话管理
- 单例 Engine
- SessionLocal 工厂
- get_db_session 生成器：FastAPI 请求级会话依赖
"""

from typing import Iterable

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


# SQLite 与 MySQL 创建 engine 的可用参数不同：
#   - SQLite 不支持 pool_size / max_overflow，需要 connect_args={"check_same_thread": False}
#   - MySQL 推荐配置连接池
def _build_engine():
    url = settings.DATABASE_URL
    if url.startswith("sqlite"):
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
            echo=False,
            future=True,
        )
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=3600,
        pool_size=10,
        max_overflow=20,
        echo=False,
        future=True,
    )


engine = _build_engine()

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    future=True,
)


def get_db_session() -> Iterable[Session]:
    """请求级数据库会话生成器"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
