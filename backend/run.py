"""
本地开发启动入口
等价于命令：uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""

import uvicorn

from app.core.config import settings


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info",
    )
