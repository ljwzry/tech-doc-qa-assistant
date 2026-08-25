# Spring Boot 配置最佳实践

> 适用于智能温室大棚 IoT 项目后端服务
> 版本：Spring Boot 3.2.x  最后更新：2026-07-13

## 1. 多环境配置

实际项目通常区分开发、测试、生产等多套环境，配置差异较大。Spring Boot 通过 `Profile` 机制实现多环境隔离。

### 1.1 配置文件组织

`src/main/resources/` 下放置 `application.yml`（公共配置）+ `application-{profile}.yml`（如 `dev`/`test`/`prod`），环境差异项由 profile 文件覆盖。

### 1.2 激活方式

**方式一：配置文件指定**
```yaml
spring:
  profiles:
    active: dev
```

**方式二：命令行参数（推荐生产）**
```bash
java -jar app.jar --spring.profiles.active=prod
```

**方式三：环境变量**（容器化部署首选）
```bash
export SPRING_PROFILES_ACTIVE=prod
java -jar app.jar
```

> 也支持 JVM 系统属性 `java -Dspring.profiles.active=prod -jar app.jar`。生产环境推荐环境变量方式，避免配置硬编码到启动脚本。

## 2. HikariCP 连接池最佳配置

HikariCP 是 Spring Boot 默认数据库连接池，性能与稳定性俱佳。合理配置参数对系统吞吐至关重要。

```yaml
spring:
  datasource:
    url: jdbc:mysql://mysql:3306/greenhouse?useUnicode=true&characterEncoding=UTF-8&serverTimezone=Asia/Shanghai
    username: ${MYSQL_USER}
    password: ${MYSQL_PASSWORD}
    hikari:
      maximum-pool-size: 20
      minimum-idle: 5
      connection-timeout: 30000
      idle-timeout: 600000
      max-lifetime: 1800000
      leak-detection-threshold: 60000
```

参数详解：

| 参数 | 取值 | 说明 |
|------|------|------|
| `maximum-pool-size` | 20 | 连接池上限，按 `(QPS × 平均查询耗时) + 冗余` 估算，4 核 8G 建议范围 10~30 |
| `minimum-idle` | 5 | 最小空闲连接，与 `maximum-pool-size` 保持 1:4 比例 |
| `connection-timeout` | 30000 ms | 从池中获取连接最长等待 30 秒，超时抛 `SQLTransientConnectionException` |
| `idle-timeout` | 600000 ms | 空闲连接 10 分钟回收，须小于 MySQL `wait_timeout`（默认 28800s） |
| `max-lifetime` | 1800000 ms | 连接最长存活 30 分钟，到期主动重建，规避长连接静默断开 |
| `leak-detection-threshold` | 60000 ms | 连接被借出超 60 秒未归还，记录泄漏告警日志 |

> 经验：`maximum-pool-size` 并非越大越好，过大可能导致 MySQL 端连接数打满、上下文切换开销增加，过小则请求排队，建议通过压测确定拐点。

## 3. 日志配置

### 3.1 application.yml 日志级别

```yaml
logging:
  level:
    root: INFO
    com.greenhouse: DEBUG
    org.springframework.amqp: WARN
    com.zaxxer.hikari: WARN
  file:
    name: /data/logs/greenhouse/app.log
```

- 根级别 `INFO` 覆盖框架日志；业务包 `com.greenhouse` 开 `DEBUG` 便于排查；第三方库（Hikari、AMQP）调到 `WARN` 避免噪音。

### 3.2 logback-spring.xml

复杂场景（按天滚动、压缩）使用 `logback-spring.xml`：

```xml
<springProfile name="prod">
  <appender name="FILE" class="ch.qos.logback.core.rolling.RollingFileAppender">
    <file>/data/logs/greenhouse/app.log</file>
    <rollingPolicy class="ch.qos.logback.core.rolling.TimeBasedRollingPolicy">
      <fileNamePattern>/data/logs/greenhouse/app.%d{yyyy-MM-dd}.log.gz</fileNamePattern>
      <maxHistory>30</maxHistory>
      <totalSizeCap>10GB</totalSizeCap>
    </rollingPolicy>
    <encoder><pattern>%d{yyyy-MM-dd HH:mm:ss.SSS} [%thread] %-5level %logger{36} - %msg%n</pattern></encoder>
  </appender>
  <root level="INFO"><appender-ref ref="FILE"/></root>
</springProfile>
```

## 4. Actuator 健康检查

```yaml
management:
  endpoints:
    web:
      exposure:
        include: health,info,metrics,prometheus
  endpoint:
    health:
      show-details: when-authorized
      probes:
        enabled: true
  health:
    redis: { enabled: true }
    rabbit: { enabled: true }
```

- `include`：仅暴露必要端点，避免敏感信息泄露。
- `show-details: when-authorized`：健康详情需鉴权后可见，对外只显示 `UP/DOWN`。
- `probes.enabled: true`：开启 K8s liveness/readiness 子端点。

访问示例：
```bash
curl http://localhost:8080/actuator/health
# {"status":"UP"}
```

## 5. Redis 配置

Spring Boot 3.x 默认使用 Lettuce 客户端。

```yaml
spring:
  data:
    redis:
      host: redis.greenhouse.local
      port: 6379
      password: ${REDIS_PASSWORD}
      timeout: 5000ms
      lettuce:
        pool: { max-active: 16, max-idle: 8, min-idle: 2, max-wait: 2000ms }
```

参数说明：`timeout: 5000ms`（命令超时，超时抛 `RedisCommandTimeoutException`）、`max-active: 16`（连接池上限，常规业务 8~32）、`max-wait: 2000ms`（池满最长等待，超时抛异常）。

> Lettuce 默认单连接共享（非池化）即可支撑高并发，连接池主要解决阻塞命令场景。若全部为非阻塞命令，可关闭连接池。

## 6. RabbitMQ 配置

```yaml
spring:
  rabbitmq:
    host: rabbitmq.greenhouse.local
    port: 5672
    username: ${RABBITMQ_USER}
    password: ${RABBITMQ_PASSWORD}
    virtual-host: /greenhouse
    publisher-confirm-type: correlated
    publisher-returns: true
    template: { mandatory: true }
    listener:
      simple:
        acknowledge-mode: manual
        prefetch: 10
        concurrency: 5
        max-concurrency: 10
```

参数说明：`acknowledge-mode: manual`（手动 ACK，失败 `basicNack` + 死信）、`prefetch: 10`（每消费者最多 10 条未确认）、`concurrency: 5`（初始线程，`max-concurrency: 10` 动态扩容）、`publisher-confirm-type: correlated`（发布确认）+ `publisher-returns + mandatory`（找不到队列回退，避免静默丢弃）。

## 7. 配置安全

- 敏感字段（密码、密钥）通过环境变量或外部配置中心（Nacos、Apollo）注入，禁止明文写入 `application.yml`。
- 配置文件纳入 Git 时使用 `Jasypt` 加密：`ENC(xxxxx)`，启动时通过 `jasypt.encryptor.password` 解密。
- 生产环境关闭 `management.endpoints.web.exposure.include=*`，仅暴露 `health,info`。
- `application-prod.yml` 不打进镜像，通过 `--spring.config.additional-location` 外挂。

## 8. 启动优化

- 开启懒加载：`spring.main.lazy-initialization=true`（开发环境加速启动；生产不建议，避免运行时突发延迟）。
- 排除未用自动配置 `@SpringBootApplication(exclude = { ... })`，调整扫描包 `@ComponentScan("com.greenhouse")`，减少 Bean 扫描开销。
- JVM 分层编译：`-XX:TieredStopAtLevel=1` 加速启动（牺牲峰值性能，适合 Serverless）。
