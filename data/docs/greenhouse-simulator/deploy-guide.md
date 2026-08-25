# 部署指南

> 智能温室大棚 IoT 项目 — 后端服务部署手册
> 适用版本：v2.1.0  最后更新：2026-07-14

## 1. 环境要求

### 1.1 运行时依赖

| 组件 | 版本 | 用途 |
|------|------|------|
| JDK | OpenJDK 17 LTS | 后端服务运行环境 |
| TDengine | 3.0.x | 时序数据存储 |
| MySQL | 8.0.x | 元数据、规则、告警日志 |
| Redis | 7.2.x | 缓存、去重、限流 |
| EMQX | 5.x | MQTT Broker |
| RabbitMQ | 3.12.x | 告警异步队列 |
| Docker | 24.0+ | 容器化部署 |
| Docker Compose | v2.20+ | 多容器编排 |

硬件建议：8 核 / 16 GB / 500 GB SSD，TDengine 数据盘独立挂载，生产环境与设备接入网段隔离。

## 2. Docker Compose 一键部署

仓库根目录提供 `docker-compose.yml`，涵盖 MySQL、Redis、EMQX、RabbitMQ、TDengine 与后端服务。

```bash
# 1. 克隆代码
git clone https://git.greenhouse.local/iot/greenhouse-backend.git
cd greenhouse-backend

# 2. 准备环境变量
cp .env.example .env
# 编辑 .env，设置 MYSQL_ROOT_PASSWORD、REDIS_PASSWORD 等

# 3. 拉取镜像并启动
docker compose pull
docker compose up -d

# 4. 查看状态
docker compose ps
```

启动顺序由 `depends_on` 与 `healthcheck` 控制：MySQL/Redis/TDengine → EMQX/RabbitMQ → backend。首次启动约需 90 秒等待依赖就绪。

## 3. 配置文件

### 3.1 application.yml 关键配置

```yaml
spring:
  profiles:
    active: ${SPRING_PROFILES_ACTIVE:dev}
  datasource:
    url: jdbc:mysql://mysql:3306/greenhouse?useUnicode=true&characterEncoding=UTF-8&serverTimezone=Asia/Shanghai
    username: ${MYSQL_USER}
    password: ${MYSQL_PASSWORD}
    driver-class-name: com.mysql.cj.jdbc.Driver
    hikari:
      maximum-pool-size: 20
      minimum-idle: 5
      connection-timeout: 30000
      idle-timeout: 600000
      max-lifetime: 1800000
      pool-name: GreenhouseHikariCP
  data:
    redis:
      host: redis
      port: 6379
      password: ${REDIS_PASSWORD}
      timeout: 5000ms
      lettuce:
        pool:
          max-active: 16
          max-idle: 8
          min-idle: 2
  rabbitmq:
    host: rabbitmq
    port: 5672
    username: ${RABBITMQ_USER}
    password: ${RABBITMQ_PASSWORD}
    listener:
      simple:
        acknowledge-mode: manual
        prefetch: 10
        concurrency: 5

tdengine:
  url: jdbc:TAOS://tdengine:6030/greenhouse?charset=UTF-8
  username: root
  password: taosdata

mqtt:
  broker: tcp://emqx:1883
  client-id: greenhouse-backend
  username: ${MQTT_USER}
  password: ${MQTT_PASSWORD}
```

HikariCP 参数说明：
- `maximum-pool-size=20`：单实例最大连接数，按 QPS 估算，单连接吞吐约 200 QPS。
- `minimum-idle=5`：最小空闲连接，避免冷启动延迟。
- `connection-timeout=30000`：获取连接超时 30 秒，超时抛 `SQLTransientConnectionException`。
- `idle-timeout=600000`：空闲连接 10 分钟回收。
- `max-lifetime=1800000`：连接最长生命周期 30 分钟，规避 MySQL `wait_timeout` 强制断开。

## 4. TDengine 数据保留策略

建库时指定保留策略：

```sql
CREATE DATABASE greenhouse
  KEEP 365
  DURATION 10
  BUFFER 16
  PAGES 256;
```

- `KEEP 365`：数据保留 365 天，超期自动清理。
- `DURATION 10`：每 10 天一个数据文件块，便于按时间分片查询与压缩。
- 生产环境若数据量极大，可将 `DURATION` 调到 30，减少小文件数量。

## 5. EMQX 认证配置

- **开发环境**：开启匿名访问（`anonymous = true`），基于 `built_in_database` 认证，便于本地联调。
- **生产环境**：启用 TLS 监听 8883，强制双向证书认证。证书由内部 CA 签发，设备出厂烧录 `device.crt` 与 `device.key`。EMQX 通过 `clientid` 与证书 CN 比对校验设备身份，关闭匿名访问。

## 6. 健康检查

后端通过 Spring Boot Actuator 暴露健康端点：

```bash
curl http://localhost:8080/actuator/health
# {"status":"UP","components":{"db":{"status":"UP"},"mqtt":{"status":"UP"},
#  "rabbit":{"status":"UP"},"redis":{"status":"UP"},"tdengine":{"status":"UP"}}}
```

Kubernetes 部署时配置：livenessProbe `/actuator/health/liveness`、readinessProbe `/actuator/health/readiness`，failureThreshold=3，periodSeconds 10/5。

## 7. 日志配置

`logback-spring.xml` 关键配置：

```xml
<configuration>
  <property name="LOG_PATH" value="/data/logs/greenhouse"/>
  <appender name="FILE" class="ch.qos.logback.core.rolling.RollingFileAppender">
    <file>${LOG_PATH}/app.log</file>
    <rollingPolicy class="ch.qos.logback.core.rolling.TimeBasedRollingPolicy">
      <fileNamePattern>${LOG_PATH}/app.%d{yyyy-MM-dd}.log.gz</fileNamePattern>
      <maxHistory>30</maxHistory>
      <totalSizeCap>10GB</totalSizeCap>
    </rollingPolicy>
    <encoder><pattern>%d{yyyy-MM-dd HH:mm:ss.SSS} [%thread] %-5level %logger{36} - %msg%n</pattern></encoder>
  </appender>
  <root level="INFO"><appender-ref ref="FILE"/></root>
  <logger name="com.greenhouse" level="DEBUG"/>
</configuration>
```

- 日志级别：根 `INFO`，业务包 `com.greenhouse` 开 `DEBUG`。
- 文件按天滚动，保留 30 天，单文件压缩为 `.gz`，总量上限 10 GB。

## 8. JVM 参数建议

启动脚本 `start.sh` 关键参数：

```bash
java -Xms512m -Xmx1024m -XX:+UseG1GC -XX:MaxGCPauseMillis=200 \
  -XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=/data/dumps/ \
  -Xlog:gc*:file=/data/logs/gc/gc.log:time,uptime:filecount=10,filesize=10m \
  -jar greenhouse-backend.jar --spring.profiles.active=prod
```

- `-Xms512m -Xmx1024m`：初始堆 512 MB，上限 1 GB，避免堆动态扩张引起停顿。
- `-XX:+UseG1GC`：G1 收集器，适合多核短停顿场景，目标停顿 200ms。
- OOM 时自动 dump 到 `/data/dumps/`，GC 日志滚动保留 10 个文件。

## 9. 部署后验收

1. 健康检查端点返回 `UP`，所有组件（db/mqtt/rabbit/redis/tdengine）状态正常。
2. 模拟设备发送一条数据，确认 TDengine 落库成功。
3. 触发一条告警规则，确认邮件/企业微信收到通知，且延迟 < 3 秒。
4. 压测：1000 设备并发上报，持续 10 分钟，后端 CPU < 70%、内存 < 1 GB。
5. 滚动重启后端，确认 MQTT 重连、RabbitMQ 消费恢复正常。
