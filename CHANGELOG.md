# 慧眼医学教学实训平台 · 版本更新记录 (Changelog)

本文档记录了平台自纳入 Git 版本管理以来的所有版本迭代内容与改动详情。

## [v4.2] - 2026-09-23

### 🎯 版本概述
**教师端功能全量版（未精简版）**。本版本完整集成了面向眼科带教老师的全套教学工具链，包括正式考试管理系统、班级分组与学员进度大盘、教学大纲指引体系、病例批量导入工具与全链路多角色测试覆盖。

### ✨ 新增功能 (Added)
- **正式考试系统 (`exams.vue` / `exam.py` / `models/exam_paper.py` / `services/exam_service.py`)**：
  - 完整支持正式考核试卷创建、自选/随机抽题组卷、考试倒计时与答题防作弊限制；
  - 自动打分与试卷提交评定记录归档。
- **班级学生与带教分组管理 (`class-students.vue` / `services/rotation_service.py`)**：
  - 支持按年级、轮转批次、带教组批量维护规培学员信息并动态计算组别进度。
- **教学大纲指引视图 (`TeachingOutlineView.vue` / `utils/teaching-outline.ts`)**：
  - 结构化展示规培教学要点与眼底病种分类考核指引。
- **病例批量导入工具 (`CaseBatchImportDialog.vue` / `services/case_import_service.py`)**：
  - 支持带教老师与管理员批量导入眼底影像与标注数据。
- **全链路自动化测试扩展**：
  - 新增正式考试流程测试 (`test_formal_exam.py`)、病灶多维度评分测试 (`test_lesion_scoring.py`)、质控与审核联动测试 (`test_quality_review_link.py`)、教学答案脱敏测试 (`test_teaching_hide_answers.py`) 等。

### 🔨 优化与调整 (Changed / Fixed)
- **教师首页学员大盘优化 (`home.vue`)**：
  - 完善全班练习次数、完成病例、平均成绩与学时统计，支持多维度组别过滤与错题统计。
- **审核链路归拢与重构**：
  - 废弃冗余的独立待审入口，将作业批改流对齐到工作台与管理后台。
- **权限与数据一致性对齐**：
  - 强化教师端教学分享、演示病例查看与病例浏览中的权限判定与状态同步。

---

## [v4.1] - 2026-09-22

### 🎯 版本概述
本版本全面聚焦**学员端问题修复与规培实训体验升级**。针对规培学员临床实训反馈，修复阅片工作站交互与 AI 诊断/质控异常，新增轮转任务首页、理论知识自测体系、病灶定位引导及多样化笔记文档展示。

### ✨ 新增功能 (Added)
- **规培轮转实训首页 (`views/training/home.vue` / `rotation.py`)**：
  - 新增学员专属轮转学习任务大盘，支持展示今日学习任务、必做病例、轮转截止时间与达标进度追踪。
- **理论自测与综合题库 (`services/text_quiz.py` / `models/text_quiz_attempt.py`)**：
  - 补充理论文本试题考核体系，支持知识点选择、填空客观题自测与评测留痕。
- **病灶定位指引练习 (`utils/finding-locate.ts`)**：
  - 勾选征象（微动脉瘤、出血、渗出等）后引导学员在眼底图上指出至少一处典型位置。
- **富文本笔记与学习资料增强 (`NoteContentView.vue` / `utils/note-content.ts`)**：
  - 学习资料支持多样化笔记格式展示，优化未解析格式与资料文件的直接下载交互。

### 🔨 优化与修复 (Fixed / Changed)
- **阅片工作站交互深度修复 (`CoreRetinaStation.vue` / `ReadingToolbar.vue` / `DiagnosisForm.vue`)**：
  - 修复切换工具后恢复指针状态、金标准图层/原图/病灶标注图层切换不生效问题；
  - 修正做题评分与准确率指标语义，避免初始状态出现默认 DR 等级与误导性 100% 得分。
- **左右眼判定与显示修正 (`eye_infer.py` / `case_utils.py`)**：
  - 修正单张眼底图像误识别为双眼的问题，增强单侧眼别推断与数据库对齐能力。
- **AI 辅助诊断与影像质控容灾优化 (`csu_eyes_client.py` / `diagnosis_service.py` / `image_quality_service.py`)**：
  - 优化质控评估与 AI 诊断调用超时与失败降级策略，提供平滑友好提示。
- **自主练习与带教评审流解耦 (`practice_service.py` / `student-teaching.vue` / `student-reviews.vue`)**：
  - 区分自主练习与正式考核，优化练习自评闭环与演示病例教学步骤。

---

## [v4] - 2026-09-17

### 🎯 版本概述
全系统代码综合收敛与完善。重构并升级了**登录重要通知弹窗与未读管理**机制，统一了传统登录与 OIDC 单点登录的通知触发流程，完善了带教评审与消息中心全链路。

### ✨ 新增与重构 (Added / Refactored)
- **登录重要通知管理体系 (`login-notice.ts` / `LoginNoticeDialog.vue`)**：
  - 新增 `login-notice.ts` 工具模块，抽离登录通知判断、已读标记与防刷规则；
  - 重构登录提示弹窗 `LoginNoticeDialog.vue`，优化通知展示、多条通知翻页及“我已知晓”已读交互逻辑。
- **通知服务与状态同步 (`notice_service.py` / `schemas/common.py`)**：
  - 后端规范化通知数据契约，强化已读时间戳记录与未读数量查询性能。
- **统一身份接入链路对齐 (`login/index.vue` / `oidc-callback.vue`)**：
  - 对齐普通账号密码登录与 OIDC 单点登录（Keycloak）成功后的通知拉取流程，确保任何入口登录均能精确触发关键通知。
- **测试用例覆盖扩充 (`test_notice_read.py` / `test_teacher_review_list.py`)**：
  - 扩充测试用例，覆盖登录通知读取标记、幂等性防护与带教评审列表组合查询。

### 🔨 优化与微调 (Changed)
- 优化带教实训待审列表与质控面板细节交互；
- 更新用户状态管理（`stores/user.ts`）与门户导航（`TrainingPortal.vue`），提升组件通信稳定性。

---

## [v3] - 2026-09-17

### 🎯 版本概述
本版本重点针对**阅片工作站交互**、**带教评审闭环**以及**学员反馈体验**进行了深度优化与功能补齐。

### ✨ 新增功能 (Added)
- **阅片质控面板 (`ReadingQualityPanel.vue`)**：
  - 在阅片工作站中新增影像质控组件，提供眼底图像质量（清晰度、曝光、视盘覆盖度）的实时评估与合规指引。
- **带教评审弹窗 (`ReadingReviewDialog.vue`)**：
  - 为带教老师提供结构化批阅界面，支持评分、评语录入、典型病灶标注指引。
- **学员评审反馈页面 (`student-reviews.vue`)**：
  - 新增学员专属评审查看页，学员可查看历史实训报告的老师打分、批注及驳回修改建议。
- **自动化测试用例 (`test_teacher_review_list.py`)**：
  - 新增带教审核列表的后端单元测试，覆盖按状态筛选、权限隔离等边界场景。

### 🔨 优化与修复 (Changed / Fixed)
- **实训状态机完善 (`reading_service.py` / `practice_service.py`)**：
  - 修复老师驳回后学员无法在同一记录上重新编辑提交的问题，实现“提交 ➔ 驳回 ➔ 重新提交”完整闭环。
- **阅片主工作台重构 (`reading/index.vue`)**：
  - 整合质控面板与审核弹窗，优化工具栏交互与标注图层切换响应速度。
- **个人中心与实训入口打通**：
  - 在个人中心增加最新评审提醒，实训列表支持高亮展示待整改报告。

---

## [v2] - 2026-09-16

### 🎯 版本概述
重大业务功能版本。新增完整的多角色用户管理中枢、学员自主注册审批流程、站内通知系统，并正式归档了全平台端到端业务流程图。

### ✨ 新增功能 (Added)
- **用户管理中枢 (`admin_users.py` / `UsersSection.vue`)**：
  - 管理后台新增用户管理列表，支持管理员进行账号的新增、编辑、禁用/启用、重置密码及部门角色分配。
- **学员自主注册与审核流 (`student_application.py` / `StudentApplicationsSection.vue`)**：
  - 新增学员申请注册入口（`apply-student.vue`）；
  - 管理后台新增学员审核列表，支持审核通过（自动开通账号并触发通知）或驳回。
- **短信通知集成 (`sms_service.py`)**：
  - 引入短信服务模块，支持在账号开通、重置密码时下发短信凭据。
- **站内通知中心 (`NotificationInbox.vue` / `LoginNoticeDialog.vue`)**：
  - 新增用户收件箱，支持系统广播与个人通知查看；
  - 登录时自动弹窗提醒重要未读消息，已读状态落库持久化。
- **端到端业务流程图 (`docs/慧眼平台-端到端业务流程图.drawio`)**：
  - 归档了全平台完整的视觉化业务流向图，涵盖影像接入、AI 辅助、学员阅片、带教考核全链路。

### 🗄️ 数据库变更 (Database Migrations)
- **迁移脚本 `0016_student_application_and_must_change_password.py`**：
  - 新建 `sys_student_application`（学员申请表）；
  - `sys_user` 表新增 `must_change_password` 字段，支持首次登录强制修改初始密码。

---

## [v1] - 2026-09-16

### 🎯 版本概述
平台基线版本（原始工程云端归档）。

### 📦 核心能力基线
- **前端工作站 (Vue 3 + TypeScript + Vite + Element Plus)**：
  - 基于 Cornerstone3D 的眼底高精度医学影像加载与画布交互（平移、缩放、多边形病灶标注、测量）；
  - AI 辅助诊断推理结果叠加展示；
  - 模拟患者档案与病例浏览中心。
- **后端架构 (FastAPI + SQLAlchemy + Alembic)**：
  - 统一认证鉴权（JWT / OAuth2 / OIDC Keycloak 对接）；
  - 完整的眼科病例管理、实训练习评分规则引擎；
  - 自动化测试套件（350+ 项单元测试与集成测试通过）。
- **工程化与部署 (Docker)**：
  - 规范化的 `.gitignore` 机制；
  - 具备 PACS (Orthanc) 影像归档与 Moodle LTI 1.3 教学平台集成基础。

---

*后续版本更新请遵循本规范持续向下追加。*
