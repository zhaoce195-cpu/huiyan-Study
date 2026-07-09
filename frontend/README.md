# 慧眼医疗云平台 V2.0 — 前端工程

> 糖尿病视网膜病变 AI 辅助筛查 + 眼科医学影像培训考核
> Vue 3 + TypeScript + Vite + Element Plus + Pinia

---

## 📌 项目概述

| 项 | 内容 |
|---|---|
| 项目名称 | 慧眼医疗云平台 V2.0（Huiyan Medical Cloud） |
| 业务场景 | 糖尿病视网膜病变（DR）AI 筛查 + 眼科住培医师标准化阅片培训 |
| 技术栈 | Vue 3.5 + TypeScript 6 + Vite 8 + Element Plus 2.14 + Pinia + Vue Router |
| 双场景 | ① 体检筛查端（浅色 · 鹰瞳风格） ② 医学培训端（深色 · ChatZOC 风格） |
| 后端协议 | REST + JSON · 默认对接 FastAPI（http://127.0.0.1:8000） |

---

## 🛠 环境要求

| 软件 | 版本 |
|---|---|
| Node.js | >= 18.x（推荐 20 LTS） |
| npm | >= 9.x（或 pnpm 8 / yarn 1） |
| 浏览器 | Chrome / Edge ≥ 100，Safari ≥ 15 |
| Nginx | >= 1.20（生产部署） |

---

## 🚀 三步快速启动（本地开发）

```bash
# 1. 安装依赖
npm install

# 2. 启动开发服务器（默认 http://localhost:5173）
npm run dev

# 3. 浏览器自动打开。默认演示账号：
#    admin / 123456    （管理员，全权限）
#    doctor / 123456   （医师，全权限）
#    trainee / 123456  （住培学员，仅医学培训端）
```

> 💡 后端未启动时，登录会自动进入"演示模式"，所有 API 失败均有本地 mock 兜底，可纯前端演示。

---

## 📦 生产构建

```bash
# 类型检查 + 生产构建（输出到 dist/，自动生成 .gz / .br 预压缩文件）
npm run build

# 本地预览构建产物（http://localhost:4173）
npm run preview
```

构建产物结构：

```
dist/
├── index.html
├── assets/
│   ├── js/         # JS 分包（带 hash，强缓存）
│   ├── css/        # 样式
│   ├── img/        # 图片
│   └── fonts/      # 字体
└── *.gz / *.br     # 预压缩文件（Nginx gzip_static / brotli_static 直接返回）
```

---

## 🌐 环境变量

在项目根目录创建 `.env.development` / `.env.production` / `.env.staging` 等文件：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `VITE_APP_TITLE` | `慧眼医疗云平台 V2.0` | 浏览器标签标题 |
| `VITE_API_BASE_URL` | `/api` | 前端请求前缀，开发时被代理转发，生产时由 Nginx 转发 |
| `VITE_API_PROXY_TARGET` | `http://127.0.0.1:8000` | 仅开发环境：vite dev server 代理目标 |
| `VITE_PUBLIC_BASE` | `/` | 部署到子路径时改（如 `/huiyan/`） |

> 修改环境变量后必须重启 dev server / 重新 build 才生效。

---

## 🏗 部署到 Nginx 服务器

### 一、上传产物

```bash
# 在本地构建
npm run build

# 把 dist/ 内容传到服务器
scp -r dist/* user@server:/usr/share/nginx/html/
```

### 二、配置 Nginx

把项目根目录下的 `nginx.conf` 复制到 `/etc/nginx/conf.d/huiyan.conf`，按需修改：

```nginx
upstream huiyan_backend {
    server 127.0.0.1:8000;          # ← 改成你的 FastAPI 后端地址
}

server {
    listen 80;
    server_name huiyan.example.com; # ← 改成你的域名 / IP
    root /usr/share/nginx/html;     # ← 前端文件存放目录
    ...
}
```

### 三、检查并重载

```bash
# 检查语法
sudo nginx -t

# 平滑重载
sudo nginx -s reload

# 或重启
sudo systemctl restart nginx
```

### 四、关键能力清单（已在 nginx.conf 中实现）

| 能力 | 实现位置 |
|---|---|
| Vue 3 history 路由刷新 404 修复 | `try_files $uri $uri/ /index.html` |
| 静态资源强缓存（1 年 + immutable） | `location ~* ^/assets/...` |
| index.html 永不缓存（发版立即生效） | `location = /index.html` |
| gzip / brotli 压缩 | `gzip on` + `gzip_static on` |
| 后端反向代理（去掉 /api 前缀） | `location /api/` |
| 大文件上传（200MB） | `client_max_body_size 200M` |
| 安全响应头 | `X-Frame-Options` / `X-Content-Type-Options` |

---

## 🐳 Docker 部署（可选）

创建 `Dockerfile`：

```dockerfile
# 多阶段构建
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

构建并运行：

```bash
docker build -t huiyan-frontend:v2.0.0 .
docker run -d -p 80:80 --name huiyan-fe huiyan-frontend:v2.0.0
```

---

## 📂 工程结构

```
huiyan-cloude/
├── public/                   # 静态资源（不会被打包处理）
├── src/
│   ├── api/                  # 接口封装层
│   │   ├── login.ts
│   │   ├── screening.ts      # 体检筛查端 API
│   │   ├── training.ts       # 医学培训端 API
│   │   ├── common.ts         # 字典/医院/通知等
│   │   └── index.ts          # 命名空间统一出口
│   ├── utils/
│   │   └── request.ts        # axios 封装（拦截器/token/错误处理/下载）
│   ├── styles/
│   │   └── var.css           # 医疗级 UI 设计 token
│   ├── router/
│   │   └── index.ts          # 路由 + 角色权限守卫
│   ├── views/
│   │   ├── login/index.vue   # 登录页
│   │   ├── screening/index.vue # 体检筛查端（鹰瞳 Airdoc 风格）
│   │   └── training/index.vue  # 医学培训端（ChatZOC 风格 + Canvas 工作站）
│   ├── layout/
│   │   └── index.vue         # 双场景首页（角色权限控制）
│   ├── App.vue
│   └── main.ts               # 入口（Pinia + Router + Element Plus）
├── .env.development          # 开发环境变量
├── .env.production           # 生产环境变量
├── nginx.conf                # ⚠ 生产部署配置
├── vite.config.ts            # ⚠ Vite 构建配置（含 gzip/brotli/分包）
├── tsconfig.app.json
├── package.json
└── README.md                 # 本文档
```

---

## 🎨 业务能力速览

### 体检筛查端（admin / doctor）
- 批量拖拽上传（支持文件夹递归）+ 上传进度条
- AI 自动 DR 分级 → 红黄绿三色风险等级排序
- 任务队列：状态/风险/置信度/送检机构
- 单份报告 PDF 导出 + 汇总报告导出
- 重新分析 / 一键转诊 / 任务移除

### 医学培训端（admin / doctor / trainee）
- **PACS 级 4 层独立 Canvas**：原图 / 标注 / AI 热力图 / 金标准
- **标注工具**：矩形 / 多边形 / 自由画笔 + 撤销 / 重做 / 清空
- **鼠标交互**：滚轮缩放（光标锚点）+ 拖拽平移 + 双击复位
- **键盘快捷键**：V/R/P/B 切换工具，Ctrl+Z/Y 撤销重做，0 适应窗口
- 病例列表 + DR 0~4 级筛选
- 提交标注 → IoU 评分 + 教师点评
- AI 虚拟导师对话（关键词智能回复 + 快捷追问）

### 登录与权限
- 演示模式自动兜底（后端不可达时）
- 三角色：`admin` / `doctor` / `trainee`
- 路由级守卫：`trainee` 无法通过 URL 访问 `/screening`
- UI 级渲染：学员首页只显示培训端单卡片

---

## 🔧 常用脚本

```bash
npm run dev        # 开发模式
npm run build      # 类型检查 + 生产构建
npm run preview    # 预览生产构建产物
```

---

## ❓ 常见问题

### 1. 部署后刷新页面 404？
确认 `nginx.conf` 中包含 `try_files $uri $uri/ /index.html`，并执行 `nginx -s reload`。

### 2. 接口跨域？
- 开发环境：通过 `vite.config.ts` 的 `server.proxy` 解决
- 生产环境：由 `nginx.conf` 中的 `location /api/` 反向代理统一收口，前后端同源

### 3. 修改 `.env.production` 不生效？
环境变量在构建时静态替换，必须**重新执行 `npm run build`** 生成新产物。

### 4. 接入子路径部署（如 `https://x.com/huiyan/`）？
1. `.env.production` 加 `VITE_PUBLIC_BASE=/huiyan/`
2. `nginx.conf` 把 `location /` 改为 `location /huiyan/`，并对应调整 `try_files`
3. 重新 build + reload

### 5. 上传超时 / 413 报错？
增大 Nginx `client_max_body_size`（已设置 200M），并确认 `proxy_read_timeout` 充足。

---

## 📞 支持

- 项目交付负责人：前端 Lead
- 技术问题反馈：通过项目 Issue / 内部协同工具
- 相关文档：[项目交付清单 DELIVERY.md](./DELIVERY.md)

---

© 慧眼医疗 · 国家三类医疗器械软件备案 · 数据加密传输
