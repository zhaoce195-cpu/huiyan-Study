# 慧眼教学云后端服务（backend）

> Python · FastAPI · SQLAlchemy · MySQL · JWT
> 与同仓库前端 Vue3 工程（`../frontend`）通过 RESTful API 对接

---

## 📌 项目特性

- 🚀 **FastAPI 高性能异步框架**，自动生成 Swagger / Redoc 文档
- 🔐 **JWT 鉴权** + **BCrypt 密码哈希** + 服务端令牌黑名单
- 🧱 **分层架构**：配置层 / 数据库层 / Schema 校验层 / 路由层 / 业务层 / 工具层 严格解耦
- 🎯 **三角色精简模型**：`STUDENT` 学员 · `TEACHER` 带教老师 · `ADMIN` 管理员
- 🛠 **统一响应封装** `{ code, msg, data }`，与前端拦截器无缝对接
- 🖼 **头像上传**：扩展名白名单 + 大小校验 + Pillow 重编码（防伪装攻击）
- 📦 **Alembic 数据库迁移** + 一键 SQL 初始化脚本

---

## 🗂 目录结构

```
backend/                         # 当前目录（D:\huiyan cloude\backend\）
├── alembic/                    # 数据库迁移
│   ├── versions/
│   ├── env.py
│   └── script.py.mako
├── alembic.ini
├── app/
│   ├── __init__.py
│   ├── main.py                 # ⭐ 入口：FastAPI 实例 / 中间件 / 路由汇总
│   ├── core/
│   │   ├── config.py           # 全局配置（pydantic-settings）
│   │   ├── security.py         # JWT 签发 / 解析 / 密码哈希 / 黑名单
│   │   └── dependencies.py     # 登录鉴权依赖、角色权限工厂
│   ├── db/
│   │   ├── base.py             # SQLAlchemy 声明式基类
│   │   ├── session.py          # Engine / SessionLocal
│   │   └── models/
│   │       ├── role.py
│   │       ├── user.py
│   │       └── user_setting.py
│   ├── schemas/                # Pydantic 入参 / 出参
│   │   ├── user.py
│   │   └── setting.py
│   ├── api/
│   │   └── v1/
│   │       ├── router.py       # v1 子路由汇总
│   │       ├── login.py        # 登录 / 登出
│   │       └── user_center.py  # 个人中心全套
│   ├── services/
│   │   ├── auth_service.py     # 登录认证业务
│   │   └── user_service.py     # 个人中心业务
│   ├── common/
│   │   ├── response.py         # 全局响应封装
│   │   └── utils.py            # 头像 / 文件工具
│   └── static/
│       └── avatars/            # 头像存储
├── .env.example                # 环境变量模板
├── .env                        # 实际配置（git 忽略）
├── init.sql                    # MySQL 一键建库建表脚本
├── init_data.py                # Python 数据初始化脚本（推荐）
├── run.py                      # 本地启动入口
├── requirements.txt
└── README.md                   # 本文件
```

---

## ⚙️ 环境要求

| 软件 | 版本 |
|---|---|
| Python | 3.10+ |
| MySQL  | 5.7+ / 8.0（推荐） |
| pip    | 最新 |

---

## 🚀 五步启动（首次部署）

### 1️⃣ 创建虚拟环境

```bash
cd "D:\huiyan cloude\backend"
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
```

### 2️⃣ 安装依赖

```bash
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
```

### 3️⃣ 配置 `.env`

```bash
copy .env.example .env       # Windows
# 或
cp .env.example .env         # macOS / Linux
```

打开 `.env`，重点修改：

```ini
DB_HOST=127.0.0.1
DB_USER=root
DB_PASSWORD=你的MySQL密码
DB_NAME=edu_eye
SECRET_KEY=请用 openssl rand -hex 32 生成新值
```

### 4️⃣ 初始化数据库

**方式 A · 推荐**（自动建表 + 写入演示账号）

```bash
# 先在 MySQL 中创建数据库（任选其一）：
mysql -uroot -p -e "CREATE DATABASE IF NOT EXISTS edu_eye DEFAULT CHARSET utf8mb4;"

# 再用 Python 初始化所有表 + 默认角色 + 演示账号
python init_data.py
```

**方式 B · 纯 SQL**

```bash
mysql -uroot -p < init.sql
```

> 演示账号（密码均含字母+数字组合，已通过强度校验）：
> - `admin` / `Admin@123`     · 管理员
> - `teacher` / `Huiyan@123`   · 带教老师
> - `student` / `Huiyan@123`   · 学员

### 5️⃣ 启动服务

```bash
python run.py
# 或
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

启动后访问：

| 入口 | URL |
|---|---|
| Swagger UI 在线文档 | <http://127.0.0.1:8000/docs> |
| Redoc 在线文档 | <http://127.0.0.1:8000/redoc> |
| OpenAPI JSON | <http://127.0.0.1:8000/api/v1/openapi.json> |
| 健康检查 | <http://127.0.0.1:8000/health> |
| 静态资源（头像） | <http://127.0.0.1:8000/static/avatars/xxx.webp> |

---

## 📡 API 总览

所有业务接口前缀：`/api/v1`

### 1. 账号身份登录

| 方法 | URL | 鉴权 | 说明 |
|---|---|---|---|
| POST | `/api/v1/auth/login` | ❌ | 账号密码登录 |
| POST | `/api/v1/auth/logout` | ✅ | 退出登录（令牌失效） |

### 2. 个人中心

| 方法 | URL | 说明 |
|---|---|---|
| GET  | `/api/v1/user/profile` | 当前登录用户详情 |
| PUT  | `/api/v1/user/profile` | 修改个人资料 |
| POST | `/api/v1/user/password` | 修改登录密码 |
| POST | `/api/v1/user/avatar` | 上传 / 更新头像 |
| GET  | `/api/v1/user/setting` | 获取个性化配置 |
| PUT  | `/api/v1/user/setting` | 保存主题/字体/通知配置 |

> 鉴权方式：HTTP Header `Authorization: Bearer <token>`

---

## 📦 统一响应结构

```json
{
  "code": 0,
  "msg": "success",
  "data": { /* 业务数据 */ }
}
```

| code | 含义 |
|---|---|
| 0 | 成功 |
| 401 | 未登录 / 令牌无效 / 已过期 |
| 403 | 无权限（角色不匹配 / 账号停用） |
| 422 | 参数校验失败 |
| 500 | 服务器错误 |

---

## 🧪 接口快速测试

### 登录

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"username\": \"admin\", \"password\": \"Admin@123\"}"
```

### 用 token 访问个人详情

```bash
curl http://127.0.0.1:8000/api/v1/user/profile \
  -H "Authorization: Bearer <上一步返回的 token>"
```

### 上传头像

```bash
curl -X POST http://127.0.0.1:8000/api/v1/user/avatar \
  -H "Authorization: Bearer <token>" \
  -F "file=@D:/your_photo.jpg"
```

---

## 🔁 数据库迁移（Alembic）

后续修改了模型，请使用 alembic 生成迁移而不是手改 init.sql：

```bash
# 生成新版本（自动 diff）
alembic revision --autogenerate -m "add new column xx"

# 升级到最新
alembic upgrade head

# 回退一版
alembic downgrade -1

# 查看历史
alembic history
```

---

## 🛡 安全要点

- ✅ 密码使用 **bcrypt** 哈希存储，永不明文落库
- ✅ JWT 令牌默认 12 小时过期，登出后立即加入黑名单
- ✅ 头像文件经 Pillow 解码 + 重编码，防止伪装恶意文件
- ✅ 对外只暴露 `/static/avatars/<文件名>`，不可越权访问其它目录
- ⚠ **生产部署请务必修改 `.env` 中的 `SECRET_KEY`**：`openssl rand -hex 32`
- ⚠ 生产环境请精确配置 `CORS_ORIGINS`，禁止使用 `*`

---

## 🐳 生产部署示例

### Gunicorn + Uvicorn Workers

```bash
pip install gunicorn
gunicorn app.main:app \
  -k uvicorn.workers.UvicornWorker \
  -w 4 \
  -b 0.0.0.0:8000 \
  --access-logfile - \
  --error-logfile -
```

### Nginx 反向代理（与前端 dist 同源部署）

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:8000/api/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    client_max_body_size 20M;
}

location /static/ {
    proxy_pass http://127.0.0.1:8000/static/;
}
```

### Docker（多阶段构建）

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## ❓ 常见问题

**Q1: 启动时报 `Can't connect to MySQL`**
检查 `.env` 中数据库配置是否正确，先确认 `mysql -uroot -p` 能登录后再启动服务。

**Q2: 前端调用 401 但 token 没过期**
确认是否携带了 `Authorization: Bearer <token>` 头；登出后旧 token 会立即失效。

**Q3: 上传头像 422**
确认 `Content-Type: multipart/form-data` 且字段名为 `file`；扩展名需在白名单内。

**Q4: 想新增字段**
1. 修改 `app/db/models/*.py`
2. `alembic revision --autogenerate -m "..."`
3. `alembic upgrade head`

---

## 📞 联系

- 项目维护：慧眼后端工程组
- 配套前端工程：`../frontend/`（Vue 3 + Vite，与本服务同仓库）

© 慧眼医疗 · 2026
