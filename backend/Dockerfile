# =================================================================
# 慧眼教学云后端 · Java (Spring Boot 3) 生产镜像
# 阶段一：Maven 依赖下载与打包
# =================================================================
FROM maven:3.9.6-eclipse-temurin-17-alpine AS builder

WORKDIR /build

# 复制 pom.xml 先行下载依赖（利用 Docker 缓存）
COPY pom.xml .
RUN mvn dependency:go-offline -B || true

# 复制源代码并进行编译打包
COPY src ./src
RUN mvn clean package -DskipTests -B

# =================================================================
# 阶段二：精简 JRE 运行环境
# =================================================================
FROM eclipse-temurin:17-jre-alpine

ENV TZ=Asia/Shanghai \
    JAVA_OPTS="-Xms256m -Xmx1024m -Djava.security.egd=file:/dev/./urandom"

WORKDIR /app

# 安装时区支持与网络探测工具
RUN apk add --no-cache tzdata wget \
    && cp /usr/share/zoneinfo/${TZ} /etc/localtime \
    && echo "${TZ}" > /etc/timezone

# 从构建阶段复制 jar 包
COPY --from=builder /build/target/*.jar app.jar

# 创建必要的持久化数据目录
RUN mkdir -p /app/app/static /app/data

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://127.0.0.1:8000/health || exit 1

ENTRYPOINT ["sh", "-c", "java ${JAVA_OPTS} -jar app.jar"]
