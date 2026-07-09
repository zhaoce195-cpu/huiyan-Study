# 慧眼 · 辅助诊断 微信小程序（uni-app Vue3）

将 Web 端「智能诊断 / 体检筛查」能力改写为微信小程序，面向**医生 / 管理员**：
拍摄或选择眼底图 → AI（CSU-EYES/DRGCNN）做 **MA 检测 / DR 分级 / 综合诊断** → 出报告、医生确认、病例检索。

## 目录结构

```
miniapp-diagnosis/
├─ pages.json            页面路由 + tabBar
├─ manifest.json         应用配置（填 mp-weixin.appid）
├─ App.vue / main.js     入口（vue3 + pinia）
├─ api/                  接口层
│  ├─ request.js         统一请求（{code,msg,data} 解包、Bearer、401 跳登录、上传封装）
│  ├─ auth.js            登录/微信登录/绑定
│  ├─ diagnosis.js       MA / DR / 综合诊断
│  └─ screening.js       病例列表 / 报告 / 确认
├─ store/user.js         登录态（pinia）
├─ utils/config.js       后端地址 & 资源 URL 拼接
└─ pages/                login / index / diagnose / result / cases / case-detail / profile
```

## 运行（推荐 HBuilderX）

1. HBuilderX 打开本目录（`miniapp-diagnosis`）。
2. `manifest.json → 微信小程序配置` 填入你的小程序 **AppID**。
3. `utils/config.js` 把 `STATIC_ORIGIN` 改成后端地址：
   - 模拟器：`http://localhost:8000`
   - 真机预览：电脑局域网 IP，如 `http://192.168.1.10:8000`
   - 上线：已在小程序后台配置的 **HTTPS 合法域名**
4. 运行 → 运行到小程序模拟器 → 微信开发者工具。
5. 开发者工具勾选 **本地设置 → 不校验合法域名/TLS**（仅本地联调用）。

### 或 CLI 方式

```bash
npm install
npm run dev:mp-weixin   # 生成 dist/dev/mp-weixin，用微信开发者工具导入
```

> CLI 依赖版本以 uni-app 官方为准；若安装报错，用 `npx degit dcloudio/uni-preset-vue#vite tmp` 校准 package.json 依赖版本。

## 登录方式

- **微信一键登录**：`wx.login` 取 code → 后端 `/auth/wechat/login` 换 openid。
  - openid 已绑定账号 → 直接登录。
  - 未绑定 → 引导输入平台账号密码，调 `/auth/wechat/bind` 绑定一次。
- **账号密码登录**：开发/兜底入口（复用 `/auth/login`）。

## 后端依赖（已在本仓库 backend 实现）

新增（向后兼容，不影响 Web 端）：
- `sys_user.wx_openid` 列（应用启动自动幂等补齐）。
- `POST /api/v1/auth/wechat/login`、`POST /api/v1/auth/wechat/bind`。
- `POST /api/v1/diagnosis/dr` 兼容 `right_eye_b64` 表单字段（小程序单文件上传限制）。

后端 `.env` 可选配置（不配则进入**开发模拟模式**，直接把 code 当 openid，便于本地联调）：

```
WECHAT_APPID=你的小程序AppID
WECHAT_SECRET=你的小程序Secret
```

## 说明

- 诊断写接口需 **TEACHER/ADMIN** 角色（与后端 `require_roles` 一致），学员/患者登录后仅可浏览。
- 后端返回的图片为相对路径 `/static/...`，已由 `utils/config.js#resolveUrl` 拼接为绝对地址。
- DR 双眼分级：微信端单次只能上传一个文件，左眼走文件、右眼走 base64，后端已兼容。
