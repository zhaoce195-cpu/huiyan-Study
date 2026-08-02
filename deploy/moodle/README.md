# Moodle 教学中台 + 慧眼 LTI 1.3 对接

方案决策二：以 Moodle 作为教学中台，慧眼作为 LTI 1.3 工具挂进去。
课程编排、班级、成绩册、考勤由 Moodle 承担，慧眼只做它不可替代的
部分 —— 影像判读训练与评分。

采用 LTI 1.3 而不是自建对接协议：不管院方现在有没有 LMS，支持这个
标准本身就是国际背书；换一家 LMS 时也不用重做集成 ——
慧眼是 Tool，LMS 是可替换件，换的时候只改一条平台注册记录。

---

## 一、起 Moodle

```bash
docker compose -f deploy/docker-compose.moodle.yml up -d
```

首次启动要建几百张表，约 5～10 分钟。等健康检查变绿：

```bash
docker inspect --format='{{.State.Health.Status}}' huiyan-moodle
```

访问 http://localhost:8081，默认管理员见 compose 里的
`MOODLE_ADMIN_USER` / `MOODLE_ADMIN_PASSWORD`。

### ⚠ 镜像是冻结的

`bitnamilegacy/moodle:5.0.2` 不再有安全更新 —— Bitnami 于 2025 年把
免费镜像迁到 bitnamilegacy 并停止维护，`bitnami/moodle` 现已没有
可拉取的公开标签。**这个镜像只适合开发与联调**。上生产三选一：

1. 订阅 Bitnami Secure Images（环境变量不变）；
2. 基于 `moodlehq/moodle-php-apache` 自建镜像，自行跟进 Moodle 版本；
3. 院方已有 Moodle 时直接对接，本文件只用于本地联调。

---

## 二、配置慧眼一侧的地址

`backend/.env`：

```
PUBLIC_BASE_URL=http://172.28.80.1:8000
FRONTEND_BASE_URL=http://172.28.80.1:5178
```

**不能用 127.0.0.1**。Moodle 跑在容器里，`127.0.0.1` 对它而言是容器自己。
`172.28.80.1` 是 Windows 主机在 WSL 网络上的地址（用
`wsl -d Ubuntu2204 -e ip route | grep default` 查）。Linux 部署时换成
实际可达的域名或内网地址。

平台要按固定地址回调，不能靠请求头推断：反向代理后面
`request.base_url` 拿到的是内网地址，平台按它跳转会直接失败。

---

## 三、注册（动态注册，推荐）

Moodle 管理员：**站点管理 → 插件 → 外部工具 → 管理工具**
（`/mod/lti/toolconfigure.php`），在「Tool URL」里粘：

```
http://172.28.80.1:8000/api/v1/lti/register
```

点 **Add LTI Advantage**，随后在工具卡片上点 **Activate**。

双方的 issuer、client_id、部署 ID、各端点地址由协议自动交换。
手工登记要填七八个字段，任何一项填错都表现为「点了没反应」，
现场排查极其费时。

脚本化（联调环境要能一条命令重建）：

```bash
cd frontend
node scripts/moodle_lti_setup.mjs http://localhost:8081 admin <口令> \
  http://172.28.80.1:8000/api/v1/lti/register
```

---

## 四、建课程与活动

Moodle 5 起不再允许「不指定预置工具」地创建 LTI 活动，URL 必须带
`typeid`。取法：

```bash
docker exec huiyan-moodle-db mariadb -umoodle -p<口令> moodle \
  -e 'SELECT id,name FROM mdl_lti_types;'
```

然后用 Moodle 自己的 PHP API 建课程活动（比点界面可靠得多，
选择器随版本变化，Moodle 5 改了不少表单）：

```bash
docker cp deploy/moodle/setup_lti_course.php huiyan-moodle:/tmp/setup.php
docker exec huiyan-moodle php /tmp/setup.php \
  <课程短名> <学员邮箱> <toolTypeId> <caseId>
```

`caseId` 通过 LTI 自定义参数 `case_id` 传给慧眼，学员点开就直接进
该病例；不填则落到病例列表 —— 不猜一个病例塞给学员。

---

## 五、身份对齐

平台侧用户按**邮箱**匹配慧眼本地账号。

默认**不自动建号**（`biz_lti_platform.auto_provision = false`）：
教学系统里凭空多出来的账号成绩归属会说不清，而且谁都能在自己的
Moodle 上装一个慧眼然后批量建号。匹配不上时给学员一页说得清的提示，
让他去找带教管理员，而不是丢一个 403。

确需自动建号时把该平台的 `auto_provision` 置为 true。自动建的账号
不设可用本地口令，只能从 LMS 启动 —— 留一个可猜的弱口令等于开后门。

角色：只认明确的教师类角色（Instructor / TeachingAssistant /
ContentDeveloper / Administrator / Mentor），其余一律按学员处理。
判断错了学员会直接看到金标准。

---

## 六、成绩回传

学员提交练习后，成绩按 LTI AGS 推送到 Moodle 作业栏。

- 平台未授予成绩服务时**如实记为未回传**，不假装成功 ——
  假装成功会让教师以为分数已经进作业栏了；
- 回传失败不影响提交：成绩已在慧眼落库，回传是集成问题，
  不该让学员的提交跟着失败；
- 每次回传结果都写进操作日志，可回溯。

---

## 七、验证

```bash
# 端点级（可进 CI，不需要 Moodle）
cd backend && python -m pytest tests/test_lti_launch.py tests/test_lti_endpoints.py -q

# 真实链路（需要 Moodle 在跑）
cd frontend && node scripts/moodle_lti_launch.mjs \
  http://localhost:8081 <学员账号> <口令> <课程id>
```

预期跳转链路：

```
课程页 → /mod/lti/auth.php → /lti-entry?token=… → /training/reading?caseId=89
```

---

## 八、生产注意事项

**必须走 HTTPS。** LTI 启动是 iframe 里的跨站 POST，state/nonce 的
Cookie 要 `SameSite=None`，而它又要求 `Secure`。HTTP 下 Cookie 会被
浏览器直接丢弃。

不过慧眼并不依赖 Cookie 才能启动：state 是用工具私钥签名的 JWT，
自带 nonce。**浏览器已在默认拦截第三方 Cookie**，只靠 Cookie 的实现
会「时好时坏」且没有任何错误提示。Cookie 能带回来时作为额外加强。

**工具私钥要作为密钥挂载。** `backend/keys/lti_tool_private.pem`
首次使用时自动生成。容器重建会换掉密钥，已登记的平台随即验签失败。
生产环境把它挂进来，不要让容器自己生成。
