"""Alembic 迁移环境

从 app.core.config.settings 动态读取数据库 URL，并使用 ORM Base.metadata 收集表结构
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings
from app.db.base import Base
import app.db.models  # noqa: F401  确保所有模型被加载

config = context.config

if config.config_file_name is not None:
    # 显式指定 UTF-8：logging 的 fileConfig 默认按系统编码读，
    # 中文 Windows 上是 GBK，ini 里只要有一个非 ASCII 字符就
    # UnicodeDecodeError，且报错完全指不到「是配置文件编码」。
    # alembic.ini 本身已保持 ASCII，这里是第二道保险。
    fileConfig(config.config_file_name, encoding="utf-8")

# 注入运行时数据库 URL
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _guard_empty_database(connection) -> None:
    """
    在空库上跑 upgrade 会失败，且报错完全指不到原因。

    本项目的迁移链是增量式的：0001 是空基线，表由 create_all() 建立。
    空库上执行 upgrade head，会在 0006 给 biz_reading_annotation 加列时
    报「no such table」—— 看起来像迁移写错了，其实是路径用错了。

    这里提前拦住，并说清该用哪条路径。
    """
    from sqlalchemy import inspect

    tables = set(inspect(connection).get_table_names())
    if tables - {"alembic_version"}:
        return
    raise SystemExit(
        "\n目标库是空的，不能直接执行 alembic upgrade。\n"
        "本项目迁移链为增量式（0001 是空基线，建表由 ORM 完成）。\n"
        "全新部署请执行：\n"
        "    python scripts/bootstrap_db.py\n"
        "它会 create_all() 建表并 stamp 到 head，此后再走 upgrade。\n"
    )


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    # 用 begin() 而不是 connect()：SQLAlchemy 2.0 起 connect() 不再隐式
    # 提交，alembic 写入 alembic_version 的那条 INSERT 会随连接关闭一起
    # 丢掉 —— 表现极具迷惑性：日志明明打印
    # 「Running stamp_revision -> 0010」，可 alembic_version 始终是空的，
    # 下次 upgrade 又从头开始跑一遍。
    with connectable.begin() as connection:
        _guard_empty_database(connection)
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
