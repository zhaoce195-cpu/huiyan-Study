# 慧眼 · 教学实训 微信小程序（uni-app Vue3）

将 Web 端「医学培训 / 阅片标注 / 学习资料」改写为微信小程序，面向**学员与带教老师**：
病例库检索 → 眼底图**阅片标注练习**（手指拖动画框标注病灶）→ 提交 **IoU 评分**与金标准对比 → 学习资料 / 个人统计。

## 目录结构

```
miniapp-teaching/
├─ pages.json / manifest.json / App.vue / main.js / uni.scss
├─ api/
│  ├─ request.js   统一请求（与诊断端一致）
│  ├─ auth.js      微信登录 / 账号绑定
│  ├─ training.js  病例库 / 标注提交 / IoU / 金标准 / 统计
│  └─ learning.js  学习资料 / 收藏 / 笔记
├─ store/user.js   登录态（pinia）
├─ utils/config.js 后端地址 & 资源 URL 拼接
└─ pages/
   ├─ login          登录 / 微信绑定
   ├─ index          首页（培训进度 + 入口 + 待练习病例）
   ├─ cases          病例库（检索 / DR 分级筛选）
   ├─ case-detail    病例详情（金标准病灶 + 进入阅片）
   ├─ reading        ★ 阅片标注（canvas 矩形标注 + IoU 评分 + 金标准对比）
   ├─ learning       学习资料列表
   ├─ resource-detail 资料详情（收藏 / 打开附件）
   └─ profile        个人中心 + 培训统计
```

## 阅片标注（reading）说明

- 选择病灶类型（出血/渗出/微动脉瘤/棉绒斑/新生血管）后，在眼底图上**手指拖动画矩形框**标注病灶。
- 支持撤销、清空、显示/隐藏金标准（绿色虚线框）、计时。
- 提交后调用 `/training/annotations/submit`，返回 IoU 评分、等级（A+/A/B/C）、各病灶漏标/误标明细。
- 坐标方案：标注点为画布显示像素，连同 `canvasWidth/canvasHeight` 上送，后端据此归一化与金标准比对。
- 当前为矩形标注（MVP）；多边形/画笔可后续在同一画布逻辑上扩展。

## 运行 / 配置

与诊断端一致：
1. HBuilderX 打开本目录，`manifest.json` 填小程序 AppID。
2. `utils/config.js` 改 `STATIC_ORIGIN` 为后端地址（模拟器 `http://localhost:8000`，真机用局域网 IP，上线用 HTTPS 合法域名）。
3. 运行到微信开发者工具，本地联调勾选「不校验合法域名」。

CLI：`npm install && npm run dev:mp-weixin`。

## 登录与权限

- 微信一键登录 / 账号密码登录（与诊断端共用后端 `/auth/wechat/login`、`/auth/wechat/bind`、`/auth/login`）。
- 培训接口对 **STUDENT/TEACHER/ADMIN** 开放；学员即可练习。带教老师/管理员额外可上传学习资料（本小程序暂以浏览为主）。

> 两个小程序共用同一套后端与登录体系；诊断端与教学端通过主题色区分（诊断蓝 / 教学青）。
