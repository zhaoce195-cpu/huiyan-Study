# 慧眼医疗云平台 · Docker Compose 部署指南

把原来「本机 uvicorn + 本机 Nginx + systemd」的部署方式，改成了两容器的 Docker Compose 架构。

## 架构

```
                        ┌─────────────────────────────┐
   浏览器  ──:8080──►   │  frontend (nginx)           │
                        │  · 托管 Vue 构建产物 dist    │
                        │  · /api/   → backend:8000   │
                        │  · /static/→ backend:8000   │
                        └──────────────┬──────────────┘
                                       │ huiyan-net (内部网络)
                        ┌──────────────▼──────────────┐
                        │  backend (FastAPI/uvicorn)  │
                        │  · /api/v1 业务接口          │
                        │  · SQLite: /app/edu_eye.db  │
                        └─────────────────────────────┘
```

- **数据库**：SQLite，零外部依赖，沿用仓库里现有的 `backend/edu_eye.db`。
- **不需要** Redis / PostgreSQL / MySQL（旧 `DEPLOY.md` 里提到的那些组件，代码实际并未使用）。

## 涉及的新增文件

| 文件 | 作用 |
| --- | --- |
| `docker-compose.yml` | 编排 backend + frontend 两个服务 |
| `.env` | Compose 变量（前端端口 / JWT 密钥 / CORS） |
| `backend/Dockerfile` | 后端镜像（python:3.12-slim + uvicorn） |
| `backend/.dockerignore` | 排除 .venv / 缓存 / 本地 .env |
| `frontend/Dockerfile` | 前端多阶段镜像（node 构建 → nginx 托管） |
| `frontend/nginx.docker.conf` | 容器内 Nginx 反代配置 |
| `frontend/.dockerignore` | 排除 node_modules / dist |

## 前置条件

安装 **Docker Desktop**（Windows / macOS）或 Docker Engine + Compose 插件（Linux）。
验证：

```powershell
docker version
docker compose version
```

## 启动

在项目根目录（`docker-compose.yml` 所在处）执行：

```powershell
docker compose up -d --build
```

首次会构建两个镜像（前端构建较慢，需联网拉 npm 依赖）。完成后访问：

- 平台首页：<http://localhost:8080>
- 后端接口（经 nginx 反代）：<http://localhost:8080/api/v1/...>

默认账号：

| 账号 | 密码 | 角色 |
| --- | --- | --- |
| admin | Admin@123 | 管理员 |
| teacher | Huiyan@123 | 带教老师 |
| student | Huiyan@123 | 学员 |

## 数据持久化

Compose 用 bind mount 把数据落到宿主机，容器重建不丢数据：

- `./backend/edu_eye.db` → 容器 `/app/edu_eye.db`（数据库）
- `./backend/app/static` → 容器 `/app/app/static`（上传的头像 / 眼底图 / 报告 PDF）

## 常用命令

```powershell
docker compose logs -f                 # 跟踪全部日志
docker compose logs -f backend         # 只看后端
docker compose ps                      # 查看容器状态
docker compose restart backend         # 重启后端
docker compose up -d --build           # 改代码后重新构建并滚动更新
docker compose down                    # 停止并移除容器（数据保留在宿主）
```

## 配置项（`.env`）

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `FRONTEND_PORT` | 8080 | 前端对外端口（宿主 → 容器 80） |
| `SECRET_KEY` | change-me... | JWT 密钥，生产务必改：`openssl rand -hex 32` |
| `CORS_ORIGINS` | 空 | 跨域白名单；同源反代时留空即可 |

## 说明 / 注意

1. **端口**：前端默认 `8080`，避开本机已占用的 `5173`/`8000`。改端口编辑 `.env` 的 `FRONTEND_PORT`。
2. **API 路径**：Nginx 反代 `/api/` 时**保留完整路径**（后端前缀就是 `/api/v1`，不能像旧 `frontend/nginx.conf` 那样剥掉 `/api`）。
3. **后端默认不对宿主暴露**，只在内部网络供前端访问。需直连调试，取消 `docker-compose.yml` 里 backend `ports` 的注释。
4. **切换到 MySQL**：把 backend 环境变量改为 `DB_TYPE=mysql` 并加 `DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME`，再在 compose 里加一个 mysql 服务即可（当前未启用）。

## 改用域名 / HTTPS

`frontend/nginx.docker.conf` 里 `server_name _;` 监听全部域名。如需 HTTPS，在该 server 块加 `listen 443 ssl;` 与证书路径，并把证书目录挂载进 frontend 容器。
