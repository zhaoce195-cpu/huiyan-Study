# =================================================================
# 慧眼教学云后端 · 生产镜像
# FastAPI + uvicorn，SQLite 零外部依赖
# =================================================================
FROM python:3.12-slim

# 时区 + Python 运行参数
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Shanghai

WORKDIR /app

# 先单独拷贝依赖清单，命中 Docker 层缓存（依赖不变则不重装）
COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

# 拷贝应用代码（.dockerignore 已排除 .venv / __pycache__ / .env 等）
COPY . .

EXPOSE 8000

# 容器内健康检查（不依赖数据库）
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0) if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).status==200 else sys.exit(1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
