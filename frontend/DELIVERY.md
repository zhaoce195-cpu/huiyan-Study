# 慧眼医疗云平台 V2.0 — 前端项目交付清单

> 本文档面向项目接收方（运维 / 后端 / 项目经理 / 验收方）。
> 列出本次交付的全部内容、验收标准、版本与责任边界。

---

## 一、交付概览

| 项 | 内容 |
|---|---|
| 项目名称 | 慧眼医疗云平台 V2.0 — 前端 |
| 交付物形态 | ① 完整前端源代码工程 ② 生产构建产物（dist 目录） ③ 部署配置文件 ④ 说明文档 |
| 交付方式 | Git 仓库 / 压缩包 |
| 交付分支 | `release/v2.0.0` |
| 版本号 | `v2.0.0` |
| 兼容浏览器 | Chrome / Edge ≥ 100，Safari ≥ 15 |
| 后端依赖 | FastAPI（REST+JSON），默认 `http://127.0.0.1:8000` |

---

## 二、交付物清单

### 2.1 源代码（必交付）

| 路径 | 说明 |
|---|---|
| `src/main.ts` | 应用入口（Pinia / Router / Element Plus / Icons） |
| `src/App.vue` | 根组件 |
| `src/router/index.ts` | 路由 + 角色权限守卫（history 模式） |
| `src/styles/var.css` | 医疗级 UI 设计 token（主色 / 风险红黄绿 / 双场景配色） |
| `src/utils/request.ts` | axios 封装（拦截器、token、错误处理、上传、下载、压缩） |
| `src/api/login.ts` | 登录接口（login / logout / userinfo / captcha / changePassword 等 6 个） |
| `src/api/screening.ts` | 体检筛查端接口（共 14 个，覆盖上传 / 分页 / 报告 / 导出 / 转诊） |
| `src/api/training.ts` | 医学培训端接口（共 12 个，覆盖病例 / 标注 / IoU / 热力图 / 金标准 / 虚拟导师） |
| `src/api/common.ts` | 通用接口（字典 / 医院 / 科室 / 通知 / 操作日志 / 系统配置 / 上传） |
| `src/api/index.ts` | API 命名空间统一出口（避免类型重名冲突） |
| `src/layout/index.vue` | 双场景首页（带角色权限渲染） |
| `src/views/login/index.vue` | 登录页（含演示模式兜底） |
| `src/views/screening/index.vue` | 体检筛查端工作台（鹰瞳 Airdoc 风格） |
| `src/views/training/index.vue` | 医学培训端阅片工作站（ChatZOC 风格 + PACS 级 Canvas 工作站） |

### 2.2 配置文件（必交付）

| 文件 | 说明 |
|---|---|
| `package.json` | 依赖与脚本清单 |
| `package-lock.json` | 锁定依赖版本（保证一致性构建） |
| `vite.config.ts` | Vite 生产配置（gzip / brotli / 分包 / DPR / Terser） |
| `tsconfig.json` / `tsconfig.app.json` / `tsconfig.node.json` | TypeScript 配置 |
| `index.html` | HTML 入口模板 |
| `.env.development` | 开发环境变量 |
| `.env.production` | 生产环境变量 |
| `nginx.conf` | Nginx 部署配置（含 history fallback + 缓存策略 + gzip + 反向代理） |

### 2.3 文档（必交付）

| 文件 | 说明 |
|---|---|
| `README.md` | 项目说明 + 启动 + 构建 + 部署完整指引 |
| `DELIVERY.md` | 本交付清单 |

### 2.4 构建产物（按需交付）

| 内容 | 说明 |
|---|---|
| `dist/` 目录 | `npm run build` 生成的可部署静态文件，含 `.gz` `.br` 预压缩文件 |

---

## 三、技术栈版本

| 依赖 | 版本 |
|---|---|
| Vue | 3.5.x |
| TypeScript | 6.0.x |
| Vite | 8.0.x |
| Element Plus | 2.14.x |
| @element-plus/icons-vue | 最新 |
| Pinia | 3.0.x |
| Vue Router | 4.x |
| axios | 1.16.x |
| vite-plugin-compression | 已集成 |
| terser | 已集成 |

---

## 四、功能交付清单

### 4.1 全局
- ✅ 登录 / 登出 / 自动 token 续期接入
- ✅ 三角色权限（admin / doctor / trainee）
- ✅ 学员仅可访问培训端（路由守卫 + UI 渲染双重控制）
- ✅ 演示模式自动兜底（后端不可达时仍可演示完整流程）
- ✅ 401 失效统一引导重新登录（防止重复弹窗）
- ✅ 全局错误统一处理（中文文案）

### 4.2 体检筛查端（鹰瞳 Airdoc 风格）
- ✅ 顶部 5 张统计卡（累计 / 高危 / 中危 / 正常 / 排队）
- ✅ 拖拽上传 + 文件夹递归 + 进度条
- ✅ 任务表格（红黄绿自动排序，分页器）
- ✅ 状态 4 态彩色 ElTag（排队 / 处理中 / 已完成 / 失败）
- ✅ 风险等级胶囊标签（红 / 黄 / 绿）
- ✅ 置信度条形进度条
- ✅ 报告预览弹窗（el-descriptions 双列）
- ✅ 单份 PDF 导出 / 汇总 PDF 导出
- ✅ 重新分析 / 一键转诊 / 移除任务
- ✅ 关键词 / 风险 / 状态过滤（支持后端筛选）

### 4.3 医学培训端（ChatZOC 风格）
- ✅ 三栏布局（病例库 / 阅片画布 / 工具+对话）
- ✅ 病例库 + DR 0/1/2/3/4 级筛选 + 难度标签
- ✅ **PACS 级 4 层独立 Canvas**
  - 原图层（程序化渲染 / 后端 URL 优先）
  - 标注层（用户绘制）
  - AI 热力图层（globalCompositeOperation: screen）
  - 金标准层（GT 虚线框）
- ✅ **图层独立开关**（含热力图透明度滑块）
- ✅ **标注工具**：矩形 / 多边形 / 自由画笔
- ✅ **撤销 / 重做 / 清空**（深拷贝快照栈，容量 80）
- ✅ **鼠标交互**：滚轮缩放（光标锚点）+ 拖拽平移 + 双击复位
- ✅ **键盘快捷键**：V/R/P/B（工具）+ Ctrl+Z/Y（撤销重做）+ 0（复位）+ Esc/Enter（多边形）
- ✅ **DPR 自适应**（HiDPI 不模糊）
- ✅ **rAF 渲染调度**（合并多帧 dirty 标记）
- ✅ **离屏画布缓存**（drawImage 复用）
- ✅ **画笔轨迹简化**（距离阈值过滤）
- ✅ **标注尺寸屏幕恒定**（lineWidth = 2 / scale）
- ✅ 病灶统计水平条形图（5 类病灶颜色编码）
- ✅ 标注列表 + IoU 评分（提交后显示，绿/蓝/橙三档）
- ✅ AI 虚拟导师对话（智能回复 + 快捷追问 + 打字气泡动画）
- ✅ 鼠标坐标实时显示（图像像素坐标）

### 4.4 登录页
- ✅ 居中医疗清爽风
- ✅ 表单验证 + 全屏 ElLoading
- ✅ 演示账号自动兜底（admin / doctor / trainee）

---

## 五、接口契约（与后端对齐项）

> 详见 `src/api/*.ts`，下面列出关键约定：

| 维度 | 约定 |
|---|---|
| 请求前缀 | `/api`（前端不带 `/api` 时由 Nginx / vite proxy 加） |
| 认证方式 | `Authorization: Bearer <token>` |
| 响应结构 | `{ code: 0/200, msg: string, data: T }` |
| 异常状态码 | `401` / `40101`：会话失效 |
| 时间字段 | 字符串 `YYYY-MM-DD HH:mm:ss` |
| 分页结构 | `{ total, page, pageSize, list[] }` |
| 文件下载 | 二进制流，前端通过 Blob 触发下载 |
| 标注坐标 | 图像原始像素坐标（与缩放/平移完全解耦） |

⚠️ **后端必须实现的关键接口**（最少集，缺一会影响主流程）：

```
POST   /api/auth/login                         登录
GET    /api/auth/userinfo                      用户信息
POST   /api/auth/logout                        登出

GET    /api/screening/tasks                    筛查任务分页
GET    /api/screening/stats                    统计
POST   /api/screening/upload/batch             批量上传
GET    /api/screening/reports/:id              报告详情
GET    /api/screening/reports/:id/pdf          导出 PDF（Blob）
POST   /api/screening/tasks/reanalyze          重新分析

GET    /api/training/cases                     病例分页
GET    /api/training/cases/:id                 病例详情
GET    /api/training/cases/:id/heatmap         AI 热力图
GET    /api/training/cases/:id/gold            金标准
POST   /api/training/annotations/submit        提交标注 → IoU
POST   /api/training/tutor/ask                 虚拟导师问答
POST   /api/training/tutor/sessions            创建会话
```

---

## 六、部署配置交付项

### 6.1 Nginx 关键能力（nginx.conf 已实现）

| 能力 | 状态 |
|---|---|
| Vue 3 history 路由刷新 404 修复 | ✅ |
| 静态资源强缓存（1 年 + immutable） | ✅ |
| index.html 永不缓存（发版立即生效） | ✅ |
| gzip 压缩（含 gzip_static 直返预压缩文件） | ✅ |
| brotli 压缩（注释保留，按需启用） | ✅ |
| `/api/` 反向代理至 FastAPI 后端 | ✅ |
| 大文件上传 200MB 上限 | ✅ |
| 安全响应头（XSS / Frame / NoSniff / Referrer） | ✅ |
| HTTPS / HSTS（注释模板） | ✅ |
| 长连接 keepalive 32 | ✅ |
| WebSocket Upgrade 支持（虚拟导师扩展可用） | ✅ |

### 6.2 Vite 构建优化

| 项 | 实现 |
|---|---|
| Terser 压缩 + 移除 console/debugger | ✅ |
| 代码分包（vendor-vue / vendor-element-plus / vendor-icons / vendor-axios） | ✅ |
| 资源分目录（js/css/img/fonts） | ✅ |
| 文件名 hash（强缓存友好） | ✅ |
| 自动生成 .gz / .br 预压缩文件 | ✅ |
| CSS 拆分（cssCodeSplit） | ✅ |
| ES2018 目标（兼容主流浏览器） | ✅ |

---

## 七、验收标准

### 7.1 启动验收

- [ ] `npm install` 无报错
- [ ] `npm run dev` 启动后无 console error
- [ ] `npm run build` 类型检查 + 构建均通过（exit 0）
- [ ] `npm run preview` 可预览生产产物

### 7.2 部署验收

- [ ] 上传 `dist/` 至 Nginx 静态目录
- [ ] `nginx -t` 语法检查通过
- [ ] 浏览器访问域名能正常加载首页
- [ ] **刷新非首页路由（如 `/screening`）不出现 404**
- [ ] 静态资源响应头包含 `Cache-Control: public, max-age=31536000, immutable`
- [ ] index.html 响应头包含 `Cache-Control: no-cache, no-store, must-revalidate`
- [ ] 响应头包含 `Content-Encoding: gzip` 或 `br`

### 7.3 业务验收

- [ ] admin / 123456 登录成功，可见双场景卡片
- [ ] doctor / 123456 登录成功，可见双场景卡片
- [ ] trainee / 123456 登录成功，**仅见培训端单卡片**
- [ ] trainee 手动访问 `/screening`，**自动重定向到 `/training`**
- [ ] 体检筛查端：可上传 / 分析 / 查看报告 / 导出 PDF
- [ ] 医学培训端：4 图层独立开关、标注、撤销重做、IoU 提交、虚拟导师对话均可用
- [ ] Canvas：滚轮缩放以光标为锚点、双击复位、Alt 拖拽平移流畅

---

## 八、责任边界

### 8.1 前端交付范围
- 前端工程代码 + 生产构建产物
- Nginx 配置模板（`nginx.conf`）
- 部署文档（`README.md`）
- 接口对接（按 `src/api/*.ts` 约定）

### 8.2 不在交付范围
- 后端服务（FastAPI）
- 数据库 / 模型 / 数据迁移
- HTTPS 证书申请与续期
- 服务器采购 / 系统初始化 / 防火墙配置
- AI 模型部署（图像分级 / 热力图生成 / IoU 计算）

---

## 九、版本与维护

### 9.1 版本号规则
遵循 [SemVer](https://semver.org/lang/zh-CN/)：`主版本.次版本.修订号`
- 主版本：不兼容的重大变更
- 次版本：向下兼容的功能新增
- 修订号：向下兼容的 bug 修复

### 9.2 当前版本
**`v2.0.0`** — 首版正式交付

### 9.3 后续维护
- bug 修复：交付方 30 天免费保修
- 功能扩展：另行评估排期

---

## 十、交付确认

| 项 | 结果 |
|---|---|
| 前端代码工程 | ☐ 已交付 |
| 生产构建产物 | ☐ 已交付 |
| nginx.conf | ☐ 已交付 |
| README.md / DELIVERY.md | ☐ 已交付 |
| 启动验收 | ☐ 通过 |
| 部署验收 | ☐ 通过 |
| 业务验收 | ☐ 通过 |

---

**交付方**：前端工程组
**接收方**：__________________
**交付日期**：__________________
**接收日期**：__________________
**双方签字**：__________________

---

© 慧眼医疗 · 国家三类医疗器械软件备案
