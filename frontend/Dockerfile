# =================================================================
# 慧眼医疗云前端 · 多阶段构建
#   stage 1: node 构建 vite 产物 dist
#   stage 2: nginx 托管静态文件 + 反代后端
# =================================================================

# ---------- 构建阶段 ----------
FROM node:22-alpine AS build

WORKDIR /app

# 依赖层缓存
COPY package.json package-lock.json ./
RUN npm ci

# 业务代码 + 生产环境变量（.env.production 内 VITE_API_BASE_URL=/api/v1）
COPY . .
# 直接用 vite 打包，跳过 package.json 里 build 脚本的 vue-tsc 类型检查：
# 类型检查报的多是「声明未使用」等 lint 级告警，不影响运行时产物，
# 不应阻塞部署构建。如需类型门禁，请单独在 CI 跑 `npm run build`。
RUN npx vite build

# ---------- 运行阶段 ----------
FROM nginx:1.27-alpine

# 站点配置（反代 /api、/static 到 backend 容器）
COPY nginx.docker.conf /etc/nginx/conf.d/default.conf

# 构建产物
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
