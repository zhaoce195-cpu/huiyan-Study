# Keycloak Realm 配置说明

> `huiyan-realm.json` 是 Keycloak 的导入文件，**不能包含任何自定义字段**——
> Keycloak 会严格校验，出现未知键（哪怕是 `_comment` 这种注释键）会直接导入失败、
> 容器反复重启。因此配置意图记录在本文档里。

对应《医学培训端评估与工作流重构报告》P0：
「登录页公开演示凭据」「无强制改密 / 限流 / 会话超时 / 失败审计」。

## 安全策略

| 配置项 | 取值 | 对应报告条目 |
|---|---|---|
| `passwordPolicy` | 至少 10 位，含大小写与数字，不得与用户名相同，禁用最近 3 次旧密码 | 强制改密 |
| `bruteForceProtected` | 连续 5 次失败锁定，等待时间指数增长，最长 15 分钟 | 登录限流 |
| `ssoSessionIdleTimeout` | 1800 秒（空闲 30 分钟失效） | 会话超时 |
| `ssoSessionMaxLifespan` | 28800 秒（最长 8 小时，覆盖一个工作班次） | 会话超时 |
| `accessTokenLifespan` | 300 秒 | 令牌短时效 |
| `eventsEnabled` / `adminEventsEnabled` | 开启，保留 30 天 | 失败审计 |
| `registrationAllowed` | false（账号由管理员分配） | 移除公开注册 |

## 客户端

| clientId | 类型 | 用途 |
|---|---|---|
| `huiyan-frontend` | 公共客户端 + PKCE(S256) | 浏览器登录 |
| `huiyan-backend` | 机密客户端 | 校验令牌、服务账号 |
| `orthanc` | 机密客户端 | PACS 作为受保护资源 |

## 角色

`STUDENT` / `TEACHER` / `ADMIN` / `PATIENT`，与现有 `RoleEnum` 一一对应，
前端的角色判定逻辑无需改动，只是改从 ID Token 的 claim 读取。

## 导入文件的两个坑

1. **不能有自定义字段**：Keycloak 严格校验导入文件，出现任何未知键
   （包括 `_comment` 这类注释键）都会导致导入失败、容器反复重启。
   配置意图只能写在本文档里。
2. **显式指定 `realmRoles` 时必须带上 `default-roles-<realm>`**：
   否则 Keycloak 不会自动补默认角色组合，用户虽然创建成功、
   状态看起来一切正常（enabled、无 requiredActions、有密码凭据），
   但登录会报 `invalid_grant: Account is not fully set up`，
   且错误信息不会指向真正原因。

3. **用户必须有 email**：Keycloak 24+ 默认启用声明式 User Profile，
   其中 email 为必填项。缺 email 的用户在管理台看起来完全正常
   （enabled、emailVerified、无 requiredActions、角色齐全），
   但登录一律返回 `invalid_grant: Account is not fully set up`，
   错误信息不指向真正原因，排查成本很高。

## 生产注意事项

1. **测试账号不进生产**：`users` 段中的 teacher / student 仅供本地验证，
   生产 realm 导入前必须删除，或改为 `temporary: true` 强制首登改密；
2. **改用生产模式**：当前 compose 用 `start-dev` + 内置 H2，
   生产须改为 `start` + 外部 PostgreSQL + HTTPS；
3. **更换客户端密钥**：`huiyan-backend-local-dev-secret` 等均为开发占位值；
4. **管理员口令**：`KC_BOOTSTRAP_ADMIN_PASSWORD: admin` 必须替换。
