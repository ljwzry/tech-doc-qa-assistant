# Project A — 部署指南

> 版本：v1.0.0 | 更新日期：2026-07-28

## 1. 环境要求

### 1.1 软件版本

| 软件 | 版本要求 | 用途 |
|------|---------|------|
| JDK | 17+ | Spring Boot 3.2 运行环境 |
| Maven | 3.9.x | Java 项目构建 |
| Node.js | 18 LTS | 前端构建与开发 |
| MySQL | 8.0.x | 业务数据库 |
| Redis | 7.2.x | 缓存、分布式锁 |
| RocketMQ | 5.0.x | 消息队列 |
| FFmpeg | 6.0.x | 视频转码（仅转码服务器需要） |
| Nginx | 1.24.x | 反向代理、静态文件托管 |
| Git | 2.x | 代码版本管理 |

### 1.2 硬件要求

| 环境 | CPU | 内存 | 磁盘 | 说明 |
|------|-----|------|------|------|
| 开发环境 | 4 核 | 8 GB | 50 GB | 单机部署全部组件 |
| 转码服务器 | 8 核 | 16 GB | 200 GB SSD | 需较高 CPU 和磁盘 IO |
| 生产环境（应用） | 4 核 | 8 GB | 50 GB | Spring Boot 实例 x2 |
| 生产环境（中间件） | 4 核 | 16 GB | 100 GB | MySQL + Redis + RocketMQ |

## 2. Docker Compose 编排

使用 Docker Compose 管理三个中间件服务，快速搭建开发/测试环境。

```yaml
# docker-compose.yml
version: '3.8'

services:
  mysql:
    image: mysql:8.0
    container_name: edu-mysql
    restart: always
    ports:
      - "3306:3306"
    environment:
      MYSQL_ROOT_PASSWORD: root123456
      MYSQL_DATABASE: edu_platform
      MYSQL_CHARACTER_SET_SERVER: utf8mb4
      MYSQL_COLLATION_SERVER: utf8mb4_general_ci
      TZ: Asia/Shanghai
    volumes:
      - mysql_data:/var/lib/mysql
      - ./scripts/init_schema.sql:/docker-entrypoint-initdb.d/init.sql:ro
    command: >
      --default-authentication-plugin=mysql_native_password
      --character-set-server=utf8mb4
      --collation-server=utf8mb4_general_ci
      --lower-case-table-names=1
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7.2-alpine
    container_name: edu-redis
    restart: always
    ports:
      - "6379:6379"
    command: redis-server --requirepass redis123456 --appendonly yes
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "redis123456", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  rocketmq-namesrv:
    image: apache/rocketmq:5.0.0
    container_name: edu-rocketmq-namesrv
    restart: always
    ports:
      - "9876:9876"
    environment:
      JAVA_OPT_EXT: "-Xms256m -Xmx256m"
    command: sh mqnamesrv

  rocketmq-broker:
    image: apache/rocketmq:5.0.0
    container_name: edu-rocketmq-broker
    restart: always
    ports:
      - "10911:10911"
      - "10909:10909"
    environment:
      JAVA_OPT_EXT: "-Xms512m -Xmx512m"
      NAMESRV_ADDR: "edu-rocketmq-namesrv:9876"
    command: sh mqbroker -n edu-rocketmq-namesrv:9876
    depends_on:
      - rocketmq-namesrv

volumes:
  mysql_data:
  redis_data:
```

启动命令：

```bash
# 启动所有中间件
docker-compose up -d

# 查看运行状态
docker-compose ps

# 查看日志
docker-compose logs -f mysql

# 停止
docker-compose down

# 停止并清除数据
docker-compose down -v
```

## 3. Spring Boot 配置

### 3.1 application.yml 核心配置

```yaml
server:
  port: 8080
  servlet:
    context-path: /
  shutdown:
    graceful: enabled  # 优雅停机

spring:
  application:
    name: edu-platform
  profiles:
    active: ${SPRING_PROFILES_ACTIVE:dev}

  # 数据源配置（HikariCP）
  datasource:
    url: jdbc:mysql://localhost:3306/edu_platform?useUnicode=true&characterEncoding=utf8mb4&useSSL=false&serverTimezone=Asia/Shanghai&allowPublicKeyRetrieval=true
    username: root
    password: root123456
    driver-class-name: com.mysql.cj.jdbc.Driver
    hikari:
      maximum-pool-size: 20
      minimum-idle: 5
      connection-timeout: 30000      # 连接超时 30 秒
      idle-timeout: 600000            # 空闲连接超时 10 分钟
      max-lifetime: 1800000           # 连接最大存活时间 30 分钟
      pool-name: EduPlatformHikariCP
      connection-test-query: SELECT 1

  # Redis 配置（Lettuce 客户端）
  data:
    redis:
      host: localhost
      port: 6379
      password: redis123456
      database: 0
      lettuce:
        pool:
          max-active: 16
          max-idle: 8
          min-idle: 2
          max-wait: 3000ms
        shutdown-timeout: 200ms

  # Jackson 全局配置
  jackson:
    date-format: yyyy-MM-dd HH:mm:ss
    time-zone: Asia/Shanghai
    default-property-inclusion: non_null

# MyBatis-Plus 配置
mybatis-plus:
  mapper-locations: classpath:mapper/**/*.xml
  type-aliases-package: com.edu.platform.model.entity
  global-config:
    db-config:
      id-type: auto
      logic-delete-field: deleted
      logic-delete-value: 1
      logic-not-delete-value: 0
  configuration:
    map-underscore-to-camel-case: true
    log-impl: org.apache.ibatis.logging.stdout.StdOutImpl  # 开发环境打印SQL

# RocketMQ 配置
rocketmq:
  name-server: localhost:9876
  producer:
    group: edu-producer-group
    send-message-timeout: 3000
    retry-times-when-send-failed: 3
  consumer:
    group: edu-consumer-group

# 阿里云 OSS 配置
aliyun:
  oss:
    endpoint: oss-cn-beijing.aliyuncs.com
    access-key-id: ${OSS_ACCESS_KEY_ID}
    access-key-secret: ${OSS_ACCESS_KEY_SECRET}
    bucket-name: edu-oss
    signed-url-expire: 3600  # 签名 URL 过期时间（秒）

# JWT 配置
jwt:
  secret: ${JWT_SECRET:edu-platform-jwt-secret-key-2026-change-in-production}
  access-token-expire: 7200     # Access Token 2 小时
  refresh-token-expire: 604800  # Refresh Token 7 天

# Actuator 健康检查
management:
  endpoints:
    web:
      exposure:
        include: health,info,prometheus
  endpoint:
    health:
      show-details: when_authorized
```

### 3.2 环境切换

```bash
# 开发环境
export SPRING_PROFILES_ACTIVE=dev
java -jar edu-platform.jar

# 生产环境
export SPRING_PROFILES_ACTIVE=prod
java -jar edu-platform.jar

# 或通过 .env 文件管理环境变量
# .env
SPRING_PROFILES_ACTIVE=dev
OSS_ACCESS_KEY_ID=LTAI5tXXX
OSS_ACCESS_KEY_SECRET=your-secret
JWT_SECRET=your-production-secret
```

## 4. Nginx 配置

### 4.1 完整配置

```nginx
# /etc/nginx/conf.d/edu-platform.conf

upstream spring_boot_backend {
    server 127.0.0.1:8080 weight=1;
    # 生产环境多实例负载均衡
    # server 127.0.0.1:8081 weight=1;
    keepalive 32;
}

server {
    listen 80;
    server_name edu-platform.com localhost;

    # 前端静态文件（Vue3 打包产物）
    location / {
        root /usr/share/nginx/html/edu-platform;
        index index.html;
        try_files $uri $uri/ /index.html;  # SPA 路由支持
    }

    # API 反向代理
    location /api/ {
        proxy_pass http://spring_boot_backend/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 10s;
        proxy_read_timeout 60s;
        proxy_send_timeout 60s;
    }

    # WebSocket 代理（转码进度推送）
    location /ws/ {
        proxy_pass http://spring_boot_backend/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 3600s;  # WebSocket 长连接
    }

    # 视频请求代理到 OSS（可选，也可前端直连 CDN）
    location /video-proxy/ {
        proxy_pass https://edu-oss.oss-cn-beijing.aliyuncs.com/;
        proxy_set_header Host edu-oss.oss-cn-beijing.aliyuncs.com;
        proxy_ssl_server_name on;
        proxy_buffering off;
        # 大文件代理超时
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }

    # 健康检查
    location /health {
        access_log off;
        return 200 "OK";
    }

    # Gzip 压缩
    gzip on;
    gzip_types text/plain text/css application/json application/javascript
               text/xml application/xml text/javascript image/svg+xml;
    gzip_min_length 1024;
    gzip_comp_level 6;

    # 静态资源缓存
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        root /usr/share/nginx/html/edu-platform;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

## 5. 日志配置

### 5.1 logback-spring.xml

```xml
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <property name="LOG_PATH" value="${LOG_PATH:-./logs}" />
    <property name="APP_NAME" value="edu-platform" />

    <!-- 控制台输出 -->
    <appender name="CONSOLE" class="ch.qos.logback.core.ConsoleAppender">
        <encoder>
            <pattern>%d{yyyy-MM-dd HH:mm:ss.SSS} [%thread] %-5level %logger{36} - %msg%n</pattern>
            <charset>UTF-8</charset>
        </encoder>
    </appender>

    <!-- 全量日志（按天滚动，保留 30 天） -->
    <appender name="FILE_ALL" class="ch.qos.logback.core.rolling.RollingFileAppender">
        <file>${LOG_PATH}/${APP_NAME}.log</file>
        <rollingPolicy class="ch.qos.logback.core.rolling.TimeBasedRollingPolicy">
            <fileNamePattern>${LOG_PATH}/${APP_NAME}.%d{yyyy-MM-dd}.log</fileNamePattern>
            <maxHistory>30</maxHistory>
            <totalSizeCap>2GB</totalSizeCap>
        </rollingPolicy>
        <encoder>
            <pattern>%d{yyyy-MM-dd HH:mm:ss.SSS} [%thread] %-5level %logger{36} - %msg%n</pattern>
            <charset>UTF-8</charset>
        </encoder>
    </appender>

    <!-- ERROR 日志单独文件（按天滚动，保留 30 天） -->
    <appender name="FILE_ERROR" class="ch.qos.logback.core.rolling.RollingFileAppender">
        <file>${LOG_PATH}/${APP_NAME}-error.log</file>
        <filter class="ch.qos.logback.classic.filter.ThresholdFilter">
            <level>ERROR</level>
        </filter>
        <rollingPolicy class="ch.qos.logback.core.rolling.TimeBasedRollingPolicy">
            <fileNamePattern>${LOG_PATH}/${APP_NAME}-error.%d{yyyy-MM-dd}.log</fileNamePattern>
            <maxHistory>30</maxHistory>
            <totalSizeCap>1GB</totalSizeCap>
        </rollingPolicy>
        <encoder>
            <pattern>%d{yyyy-MM-dd HH:mm:ss.SSS} [%thread] %-5level %logger{36} - %msg%n</pattern>
            <charset>UTF-8</charset>
        </encoder>
    </appender>

    <!-- 开发环境仅控制台 -->
    <springProfile name="dev">
        <root level="INFO">
            <appender-ref ref="CONSOLE" />
        </root>
        <logger name="com.edu.platform" level="DEBUG" />
        <logger name="com.baomidou.mybatisplus" level="DEBUG" />
    </springProfile>

    <!-- 生产环境控制台 + 文件 -->
    <springProfile name="prod">
        <root level="INFO">
            <appender-ref ref="CONSOLE" />
            <appender-ref ref="FILE_ALL" />
            <appender-ref ref="FILE_ERROR" />
        </root>
        <logger name="com.edu.platform" level="INFO" />
    </springProfile>
</configuration>
```

## 6. JVM 参数

### 6.1 开发环境

```bash
java -Xms256m -Xmx512m -jar edu-platform.jar
```

### 6.2 生产环境

```bash
java \
  -Xms512m \
  -Xmx2048m \
  -XX:+UseG1GC \
  -XX:MaxGCPauseMillis=200 \
  -XX:+HeapDumpOnOutOfMemoryError \
  -XX:HeapDumpPath=./logs/heapdump.hprof \
  -Djava.security.egd=file:/dev/./urandom \
  -Dspring.profiles.active=prod \
  -jar edu-platform.jar
```

参数说明：

| 参数 | 说明 |
|------|------|
| `-Xms512m` | 初始堆内存 512MB |
| `-Xmx2048m` | 最大堆内存 2GB |
| `-XX:+UseG1GC` | 使用 G1 垃圾回收器（适合多核、大内存场景） |
| `-XX:MaxGCPauseMillis=200` | GC 最大停顿时间目标 200ms |
| `-XX:+HeapDumpOnOutOfMemoryError` | OOM 时自动导出堆转储文件 |
| `-XX:HeapDumpPath` | 堆转储文件保存路径 |
| `-Djava.security.egd` | 解决 Linux 下随机数生成阻塞问题 |

## 7. 健康检查

### 7.1 应用健康检查

```bash
# Spring Boot Actuator 健康检查
curl http://localhost:8080/actuator/health

# 响应示例
{
    "status": "UP",
    "components": {
        "db": { "status": "UP" },
        "redis": { "status": "UP" },
        "diskSpace": { "status": "UP", "details": { "total": 107374182400, "free": 53687091200 } }
    }
}
```

### 7.2 中间件健康检查

```bash
# MySQL
mysqladmin ping -h 127.0.0.1 -u root -proot123456

# Redis
redis-cli -a redis123456 ping
# 返回 PONG 表示正常

# RocketMQ NameServer
curl http://localhost:9876/health  # 通过 mqadmin 工具检查
```

### 7.3 Nginx 配置检查

```bash
# 检查配置语法
nginx -t

# 重新加载配置（不断服务）
nginx -s reload

# 停止
nginx -s stop
```

## 8. 数据库初始化

### 8.1 初始化脚本

数据库初始化脚本位于项目根目录 `scripts/init_schema.sql`，Docker Compose 会自动挂载并执行。

手动初始化：

```bash
# 登录 MySQL
mysql -h 127.0.0.1 -u root -proot123456

# 创建数据库
CREATE DATABASE IF NOT EXISTS edu_platform
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_general_ci;

# 执行初始化脚本
USE edu_platform;
SOURCE scripts/init_schema.sql;
```

### 8.2 初始化脚本结构

```
scripts/
  +-- init_schema.sql        # DDL 建表脚本
  +-- init_data.sql          # 初始数据（管理员账号、默认分类等）
  +-- init_indexes.sql       # 索引脚本（可选单独执行）
```

### 8.3 初始数据

```sql
-- 初始管理员账号（密码：admin123，BCrypt加密）
INSERT INTO `user` (`username`, `nickname`, `password`, `role`, `status`)
VALUES ('admin', '系统管理员', '$2a$10$N.zmdr9k7uOCQb376NoUnuTJ8iAt6Z5EHsM8lE9lBOsl7iAt6Z5EH', 2, 1);

-- 课程分类初始数据
INSERT INTO `category` (`name`, `sort_order`) VALUES
('后端开发', 1), ('前端开发', 2), ('移动开发', 3),
('人工智能', 4), ('数据科学', 5), ('设计创意', 6);
```

## 9. 前端构建与部署

### 9.1 构建

```bash
# 进入前端目录
cd edu-platform-web

# 安装依赖
npm install

# 开发环境启动
npm run dev

# 生产构建
npm run build
```

### 9.2 部署前端

```bash
# 将构建产物复制到 Nginx 目录
cp -r dist/* /usr/share/nginx/html/edu-platform/

# 重载 Nginx
nginx -s reload
```

## 10. 完整启动流程

```bash
# 1. 启动中间件
docker-compose up -d

# 2. 等待中间件就绪（约 10 秒）
sleep 10

# 3. 初始化数据库（首次部署）
mysql -h 127.0.0.1 -u root -proot123456 edu_platform < scripts/init_schema.sql
mysql -h 127.0.0.1 -u root -proot123456 edu_platform < scripts/init_data.sql

# 4. 编译后端
cd edu-platform-server
mvn clean package -DskipTests

# 5. 启动 Spring Boot
nohup java -Xms512m -Xmx2048m -XX:+UseG1GC -XX:MaxGCPauseMillis=200 \
  -Dspring.profiles.active=prod \
  -jar target/edu-platform.jar > /dev/null 2>&1 &

# 6. 健康检查
sleep 15
curl http://localhost:8080/actuator/health

# 7. 部署前端
cd ../edu-platform-web
npm run build
cp -r dist/* /usr/share/nginx/html/edu-platform/
nginx -s reload

# 8. 验证
curl http://localhost/health
```
