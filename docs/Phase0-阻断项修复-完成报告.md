# Phase 0 阻断项修复 · 完成报告

> 依据：《慧眼医疗云平台_医学培训端评估与工作流重构报告_完整版》V1.0（2026-07-31）
> 方案：《慧眼医学培训端-重构技术方案-开源选型版》第 7 章 Phase 0
> 完成日期：2026-08-01　　状态：**代码未提交，待 review**

---

## 一、总览

报告 Phase 0 列出 8 项交付，本轮完成 7 项，1 项部分完成（详见第四节）。

| # | 交付项 | 状态 | 验证方式 |
|---|--------|------|----------|
| 1 | 金标准接口鉴权 hotfix | ✅ 完成 | 端到端实测 403 |
| 2 | 内容策略引擎 v1 | ✅ 完成 | 25 项单测 + 端到端实测 |
| 3 | 契约测试守卫 | ✅ 完成 | 完整性守卫测试 |
| 4 | HTTPS + HSTS | ✅ 配置完成 | 配置校验（部署待执行） |
| 5 | 移除公开凭据 | ✅ 完成 | 源码核查 |
| 6 | 安全条 v1 | ✅ 完成 | 端到端实测 + 45 项单测 |
| 7 | 不可判读状态 | ✅ 完成 | 真实故障下降级实测 + 26 项单测 |
| 8 | 分级「不适用」区分 | ⚠️ 部分 | 字段已可空，存量回填脚本待做 |

**测试**：后端 96 项全部通过；前端类型检查与改动前基线逐行 diff，未引入新错误。

---

## 二、修复详情

### 2.1 金标准接口鉴权（最严重的 P0）

**问题比报告描述更严重。** 报告认为答案泄露发生在列表字段与 DOM，实际服务端存在一个不校验作答状态的接口：

```
GET /training/cases/{caseId}/gold
  → TrainingService.get_gold(db, case_id)     # 未传 user、未校验是否已提交
```

路由仅校验角色（STUDENT 即可通过），任何登录学员可在作答前直接取回任意病例的完整金标准。

值得注意的是，该接口在前端**零调用方**——`TrainingApi.getGoldStandard` 定义了但没有任何页面使用。这个泄题面纯粹是裸露的 API，界面上看不出来，只能通过直接请求触及。这也说明仅靠前端走查无法发现此类问题。

**修复**：`get_gold` 增加 `user` 参数与「已提交作答或教师/管理员」判定，复用 practice 模块已有的正确门禁逻辑。

### 2.2 盲训内容策略引擎

新增 `backend/app/core/content_policy.py`，方案中唯一必须自研的组件。

- 四种呈现模式：`TRAINING_BLINDED` / `TRAINING_REVIEW` / `TEACHING_DEMO` / `CLINICAL`
- 模式由「场景 + 角色 + 作答状态」在服务端推导，**不接受前端或 URL 参数指定**
- 答案型字段集中登记于 `ANSWER_FIELD_BLANKS`，裁剪发生在序列化层
- 作答状态由服务端查询 `PracticeSession` 得出，列表场景批量查询避免 N+1

接入点：`case_browse_service._to_item/_to_detail`、`practice_service._to_brief`。

### 2.3 契约测试守卫

`tests/test_content_policy.py` 含一项**完整性守卫**：受保护模型（`CaseBrowseItem`、`CaseBrowseDetail`、`CaseBriefForPractice`）的每个字段必须显式归类为「答案 / 中性化 / 安全」之一，新增字段若未归类则测试失败——等价于「默认按答案处理」。

> 建议将本测试设为 CI 阻断级：不通过不允许合并。考核效度一旦回归，事后无法补救。

### 2.4 影像安全条

新增 `backend/app/common/image_safety.py` 与 `frontend/.../ReadingSafetyBar.vue`。

常驻展示：病例号、眼别（OD/OS + 中文）、检查日期、模态、图像质量、影像序号与类别、影像构成、质控状态、阅片状态。`position: sticky` 保证全屏与弹窗时不消失。

三条贯穿设计的原则——**未知即显示未知，绝不静默填充**：

| 场景 | 处理 | 理由 |
|------|------|------|
| 检查日期 | 显示「检查日期未采集」 | 现有数据模型无该字段；用 `created_at`（入库时间）冒充会让人误判检查时间 |
| 眼别无线索 | 显示「眼别未知」 | 不从文件名猜测 |
| 质量未评估 | 显示「未评估」并标黄 | 未评估 ≠ 合格 |

**眼别冲突检测**（报告 8.3 首条 P0）：元数据眼别与文件名线索交叉校验，冲突时红条横贯且不可关闭，**同时写出两个来源的取值**，系统不自动选边。

**影像混算**（报告 P1「8 张影像到底是什么」）：原图与派生对象（mask / overlay / 热力图）分别计数，原图独立编号。

### 2.5 图像质量门控

复用 CSU-EYES 已上线的 ConvNeXt 图像质量三分类模型，**不训练新模型**——这是本轮性价比最高的一项复用。

- `backend/app/services/image_quality_service.py`：评估、解析、缓存
- `backend/app/db/models/case_image_quality.py` + `alembic/versions/0005`：质量作为**派生对象**独立建表，不往 `CaseImage` 加列，便于换模型后重算与追溯
- `POST /reading/cases/{caseId}/quality-check`：教师端触发

**降级能力在真实故障下得到验证。** 开发期间 CSU-EYES 隧道恰好中断，实测结果：

```
POST /reading/cases/169/quality-check
  HTTP 200   msg = 质量评估完成
  共 1 张原图，成功 0，失败 1
  imageId=1461  quality=unknown
  error=CSU-EYES 调用失败：ConnectionResetError(10054, ...)

安全条：已质控=False · 未评估 1 张 · 不可判读 0 张
阅片页 GET source → HTTP 200，流程未被阻断
```

关键在于**没有把调用失败伪装成合格**：质量停留在 `unknown`，`qualityChecked=False` 使界面无法声称已完成质控，失败原因落库可查。这正是方案风险表要求的「降级而非阻断」。

### 2.6 传输安全与声明一致性

| 项 | 修复 |
|----|------|
| 明文 HTTP | 新增 `deploy/Caddyfile` + `docker-compose.tls.yml`，Caddy 自动签发续期证书并下发 HSTS |
| 明文旁路 | TLS 叠加配置中收回 frontend 宿主端口，外部无法绕过 Caddy 直连 |
| nginx 安全头 | 补 `Permissions-Policy`，并注明部署形态与 HSTS 归属，避免两处重复下发 |
| 公开凭据 | 删除 `login/index.vue` 的 `DEMO` 常量与页面凭据提示，输入框不再预填 |
| 不实声明 | 页脚「数据加密传输」改为按 `location.protocol` 实时判定，非加密连接时显示红色警示 |

原页脚的「国家三类医疗器械软件备案」与「符合《医疗器械数据完整性要求》」属不可追溯表述，已移除。**若确已取得注册证，请填回具体证书编号**——这是产品与法务需要确认的事项。

---

## 三、验证记录

### 3.1 盲训隔离端到端实测

| 接口 | 学员（未作答） | 教师 |
|------|----------------|------|
| `/case-browse/list` | title=`病例 IDRID-T-IDRiD_81`、drLevel=`null` | title=`IDRiD_81 · DR 3 级`、drLevel=`3` |
| `/case-browse/{id}` | goldDiagnosis=`""`、teachingPoints=`""` | 完整可见 |
| `/practice/random` | drLevel=`null`、标题中性化 | 完整可见 |
| `/training/cases/{id}/gold` | **403 请先提交本次作答** | 200 正常 |

递归扫描响应 JSON 的每一层，未发现残留答案字段；标题中不再含 DR 等级。

### 3.2 测试统计

```
backend:  96 passed
  test_content_policy.py     25   盲训策略与完整性守卫
  test_image_safety.py       45   眼别冲突、影像分类、质量文案
  test_image_quality_gate.py 26   上游解析容错、降级、质控汇总

frontend: 类型检查与基线逐行 diff，未引入新错误
```

### 3.3 关于前端类型检查的更正

此前几次报告的「vue-tsc 通过」**无效**。根 `tsconfig.json` 为 `files: []` 的引用式配置，`vue-tsc --noEmit` 跑它等于不检查——故意注入未定义变量仍返回 0。正确命令为：

```bash
npx vue-tsc -p tsconfig.app.json --noEmit
```

改用正确方式后发现并修正了一个真实缺陷：调用了不存在的 `loadSource()`，实际函数名为 `fetchSource()`。

---

## 四、遗留事项

### 4.1 Phase 0 内未完成

- **分级「不适用」存量回填**：`dr_level` 已可空，`CaseBriefForPractice` 与 `CaseBrowseItem` 均支持 `null`，但存量数据中「非 DR 病例」仍存有 `gold_dr_grade='0'`，需要一次性回填脚本区分「0 级无 DR」与「不适用」。

### 4.2 本轮发现的既有缺陷（不在报告范围，未修改）

| 缺陷 | 影响 | 位置 |
|------|------|------|
| `CaseImageApi.backfillPatientInfo` 不存在 | 管理后台「旧病例一键补齐模拟患者信息」运行时报错，功能完全不可用；后端 `admin_import` 也只有 `/idrid`，缺对应接口 | `IdridImportSection.vue:142` |
| `string \| undefined` 传入要求 `string` 的参数 | 潜在运行时异常 | `screening/case-search.vue:706` |
| 47 处未使用变量（TS6133） | 无功能影响，但掩盖真实错误 | 多文件 |

建议单独立项处理，尤其第一条是用户可见的功能损坏。

### 4.3 部署待执行

- Caddy 配置已就绪但**尚未在服务器上执行**。上线需要：确认域名、设置 `HUIYAN_DOMAIN` 与 `HUIYAN_ACME_EMAIL`、执行叠加启动命令。
- `!reset` 语法需要 Docker Compose ≥ 2.24；低版本按文件内注释改用 `FRONTEND_PORT=127.0.0.1:8080`。
- 无公网域名时可用 `tls internal`，但需向各客户端分发根证书，否则浏览器仍告警。

---

## 五、改动清单

**新增（9）**

```
backend/app/core/content_policy.py             盲训内容策略引擎
backend/app/common/image_safety.py             影像安全标识工具
backend/app/services/image_quality_service.py  质量门控服务
backend/app/db/models/case_image_quality.py    质量结果模型
backend/alembic/versions/0005_case_image_quality.py
backend/tests/test_content_policy.py
backend/tests/test_image_safety.py
backend/tests/test_image_quality_gate.py
frontend/src/views/reading/components/ReadingSafetyBar.vue
deploy/Caddyfile
docker-compose.tls.yml
```

**修改（主要）**

```
backend/app/services/training_service.py       金标准鉴权
backend/app/services/case_browse_service.py    内容策略接入
backend/app/services/practice_service.py       内容策略接入
backend/app/services/reading_service.py        安全元数据 + 质量
backend/app/services/csu_eyes_client.py        质量评估客户端
backend/app/api/v1/{training,reading}.py       鉴权透传 + 质量接口
backend/app/schemas/{case_browse,practice,reading}.py
frontend/src/views/login/index.vue             移除凭据
frontend/src/views/reading/index.vue           安全条 + 质量评估
frontend/src/layout/index.vue                  合规声明整改
frontend/src/api/{reading,case-browse,practice}.ts
frontend/nginx.conf                            安全头加固
```

---

## 六、下一步

1. **本轮代码 review 与提交**
2. **部署 HTTPS**（需确认域名）
3. **进入 Phase 1**：Keycloak 接入、Orthanc 部署与影像 DICOM 化、Cornerstone3D 替换阅片内核、Moodle 部署与身份对齐

> Phase 1 中「Moodle 部署与身份对齐」必须与 Keycloak 同期完成——身份不对齐是整个方案最大的实施风险。
