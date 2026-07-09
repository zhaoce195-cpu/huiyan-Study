# 慧眼医疗云平台 V2.0 — API 文档使用说明

本目录提供完整的 OpenAPI 3.0.3 接口规范和两套可视化文档界面。

---

## 📂 目录结构

```
docs/
├── openapi.yaml      ⭐ OpenAPI 3.0.3 规范（接口契约源文件）
├── swagger.html      Swagger UI 文档（支持在线 try-it-out）
├── redoc.html        Redoc 文档（更适合阅读 / 评审）
└── README.md         本文件
```

---

## 🚀 三种打开方式

### 方式一：本地起静态服务（推荐）

在 `docs/` 目录下任选一种命令启动：

```bash
# Node 用户
npx serve .

# Python 3 用户
python -m http.server 8080
```

然后浏览器访问：

- Swagger UI：<http://localhost:8080/swagger.html>（或 npx serve 的端口）
- Redoc：<http://localhost:8080/redoc.html>

> ⚠️ **不能直接双击 HTML 文件**用 `file://` 协议打开 —— 浏览器跨域限制会导致 yaml 加载失败。

### 方式二：丢进项目的 `public/` 目录

把 `docs/` 整个文件夹放到前端项目 `public/` 下，重新 `npm run dev` 后即可访问：

- <http://localhost:5173/docs/swagger.html>
- <http://localhost:5173/docs/redoc.html>

### 方式三：发布到任意 Web 服务器（Nginx / OSS / Pages）

直接把 `docs/` 目录上传，三个文件互相引用，无服务端依赖。

---

## 🛠 后端集成方案

### FastAPI（推荐 · 自动生成）

FastAPI 可直接读取 `openapi.yaml` 进行接口校验和文档自动生成。最简集成：

```python
# main.py
from fastapi import FastAPI
import yaml

with open('docs/openapi.yaml', 'r', encoding='utf-8') as f:
    custom_openapi = yaml.safe_load(f)

app = FastAPI(
    title="慧眼医疗云平台 V2.0",
    version="2.0.0",
    docs_url="/docs",        # FastAPI 内置 Swagger UI
    redoc_url="/redoc"       # FastAPI 内置 Redoc
)

# 用本地 yaml 覆盖自动生成的 schema
def get_openapi():
    return custom_openapi
app.openapi = get_openapi
```

启动后：
- <http://127.0.0.1:8000/docs> — Swagger UI
- <http://127.0.0.1:8000/redoc> — Redoc
- <http://127.0.0.1:8000/openapi.json> — JSON 规范

### Spring Boot

使用 `springdoc-openapi`，把 `openapi.yaml` 放到 `src/main/resources/`：

```yaml
# application.yml
springdoc:
  swagger-ui:
    url: /openapi.yaml
    path: /swagger-ui.html
```

### NestJS

使用 `@nestjs/swagger`，可加载现有 `openapi.yaml` 作为基础再扩展。

### 任意框架（无侵入）

直接把 `docs/` 目录通过 Nginx 暴露：

```nginx
location /api-docs/ {
    alias /usr/share/nginx/html/docs/;
    index swagger.html;
}
```

---

## 📋 接口总览（4 大模块 · 共 39 个接口）

| 模块 | 数量 | 主要能力 |
|---|---|---|
| **Auth · 认证** | 6 | 登录 / 登出 / 用户信息 / 刷新令牌 / 验证码 / 改密 |
| **Screening · 体检筛查** | 14 | 上传 / 任务列表 / 详情 / 删除 / 重分析 / 统计 / 报告 / PDF 导出 / Excel 导出 / 转诊 |
| **Training · 医学培训** | 12 | 病例列表 / 详情 / 标记完成 / 热力图 / 金标准 / 提交标注 / IoU 试算 / 历史 / 虚拟导师问答 / 会话 / 统计 |
| **Common · 通用** | 11 | 系统配置 / Ping / 通用上传 / 字典 / 医院 / 科室 / 通知 / 操作日志 / 服务器时间 |

---

## 🔐 鉴权说明

所有接口（除登录、刷新、验证码、系统配置、Ping 外）需要在请求头携带 token：

```http
Authorization: Bearer <token>
```

token 来自登录接口返回的 `data.token` 字段。

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
| 0 / 200 | 成功 |
| 401 / 40101 | 会话失效（前端自动跳登录） |
| 其它非零 | 业务失败（前端用 msg 提示） |

文件下载（PDF / Excel）接口直接返回二进制流，不是 JSON。

---

## 🔄 与前端契约同步

前端 API 封装位于 `src/api/*.ts`，与 `openapi.yaml` **严格一一对应**：

| 前端文件 | YAML tag |
|---|---|
| `src/api/login.ts` | Auth · 认证 |
| `src/api/screening.ts` | Screening · 体检筛查 |
| `src/api/training.ts` | Training · 医学培训 |
| `src/api/common.ts` | Common · 通用 |

修改接口时**必须同步更新两边**：
1. 改 `openapi.yaml`（接口契约）
2. 改 `src/api/*.ts`（前端调用）
3. 后端按 yaml 实现

---

## 🧪 在线调试

在 `swagger.html` 中：
1. 点击右上角 **Authorize** 按钮，输入 `Bearer <token>`
2. 选择任意接口，点 **Try it out**
3. 填入参数，点 **Execute** 即可发起真实 HTTP 调用
4. 注意 CORS：调试时 `servers` 第一个地址必须开启跨域；生产经 Nginx 同源不受影响

---

## 📥 导出 / 转换

以下命令可基于 `openapi.yaml` 生成其它格式：

```bash
# 转 JSON
npx @apidevtools/swagger-cli bundle openapi.yaml -o openapi.json

# 转 Postman Collection
npx openapi-to-postmanv2 -s openapi.yaml -o postman.json -p

# 生成 TypeScript 类型
npx openapi-typescript openapi.yaml -o ../src/types/api.d.ts

# 生成 Mock 服务（Prism）
npx @stoplight/prism-cli mock openapi.yaml --port 8000
```

> 用 Prism 可在后端没就绪时启动一个完整 Mock 服务，前端直接联调。

---

© 慧眼医疗 · 国家三类医疗器械软件备案
