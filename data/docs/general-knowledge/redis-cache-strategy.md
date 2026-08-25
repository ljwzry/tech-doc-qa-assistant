# Redis 缓存策略

> 适用于智能温室大棚 IoT 项目
> 版本：Redis 7.2.x  最后更新：2026-07-12

## 1. Redis 在本项目中的用途

Redis 作为内存数据库，在本项目中承担四类核心缓存职责，配合 TDengine / MySQL 主存储，形成"热数据走缓存、冷数据走库"的分层架构。

### 1.1 设备在线状态缓存

- Key：`device:status:{device_id}`
- Value：`{ "online": true, "last_seen": 1720605600000, "ip": "10.0.1.23" }`
- TTL：120 秒
- 用途：大屏实时展示设备在线/离线状态，避免每秒查 MQTT 会话表。
- 更新时机：MQTT 上行消息（data/status）到达时主动刷新 TTL 与 `last_seen`；TTL 过期即视为离线。

### 1.2 实时数据缓存

- Key：`data:realtime:{greenhouse_id}`
- Value：该温室下所有设备最新一条数据的聚合 JSON（温度、湿度、CO2 等）。
- TTL：10 秒
- 用途：大屏首页 10 秒刷新一次实时指标，直接命中缓存，避免重复查 TDengine `LAST()`。
- 更新时机：MQTT 数据落 TDengine 后，同步更新对应温室的实时数据缓存。

### 1.3 预警查询结果缓存

- Key：`alert:stats:{greenhouse_id}:{period}`
  - `period` 取值：`today`、`7d`、`30d`
- Value：`{ "critical": 5, "warning": 18, "info": 42, "recovered": 3 }`
- TTL：60 秒
- 用途：大屏告警统计卡片，避免每次刷新都聚合 `alert_log` 表（百万级行）。
- 更新时机：定时任务每 60 秒刷新；新告警产生时主动失效对应 Key。

### 1.4 聚合查询缓存

- Key：`data:agg:{greenhouse_id}:{metric}:{interval}:{hash}`
  - `metric`：`temperature` / `humidity` / `co2` ...
  - `interval`：`1h` / `1d` ...
  - `hash`：时间范围的 MD5（如 `2026-07-01_2026-07-07` 的 hash）
- Value：聚合结果数组 `[{ ts, avg, max, min }, ...]`
- TTL：300 秒（5 分钟）
- 用途：前端趋势图、报表查询，缓存 TDengine `INTERVAL` 聚合结果，命中率 > 70% 时查询 P95 < 500ms。
- 更新时机：首次查询未命中时回填；数据写入不主动失效（容忍 5 分钟延迟）。

## 2. 缓存更新策略

### 2.1 Cache Aside（旁路缓存）

适用：设备状态、实时数据。

```
读：先查 Redis，命中返回；未命中查 DB，回填 Redis。
写：先写 DB，再删除 Redis 对应 Key（而非更新，避免并发写覆盖）。
```

本项目设备状态采用变体——MQTT 消息到达即主动 `SET` 覆盖缓存，无需等 DB 写入完成，因为状态本身不需要持久化精度。

### 2.2 Write Through（写穿透）

适用：实时数据。

TDengine 写入成功后，同步更新 `data:realtime:{greenhouse_id}`，保证缓存与 DB 强一致。代价是写入路径增加一次 Redis 调用，但 Redis 内网延迟 < 1ms，可接受。

### 2.3 定时刷新 + 主动失效

适用：统计类数据（告警统计、聚合查询）。

- 定时任务（`@Scheduled`）周期性刷新热点 Key，避免缓存雪崩后集体回源。
- 写入侧在告警产生时 `DEL alert:stats:{gh_id}:today`，触发下次查询重新聚合。
- 聚合查询缓存不主动失效，仅依赖 TTL 自然过期，简化逻辑。

## 3. Key 命名规范

统一格式：`{业务域}:{功能}:{标识}`，用冒号 `:` 分隔。

| 业务域 | 功能 | 标识示例 | 完整 Key |
|--------|------|----------|----------|
| `device` | `status` | `{device_id}` | `device:status:dev_temp_001` |
| `data` | `realtime` | `{greenhouse_id}` | `data:realtime:gh_001` |
| `data` | `agg` | `{gh_id}:{metric}:{interval}:{hash}` | `data:agg:gh_001:temperature:1d:a1b2c3` |
| `alert` | `stats` | `{gh_id}:{period}` | `alert:stats:gh_001:today` |
| `alert` | `dedup` | `{rule_id}:{device_id}` | `alert:dedup:1001:dev_temp_001` |
| `rate` | `limit` | `{device_id}:{action}` | `rate:limit:dev_temp_001:command` |

规范要点：
- 全小写，单词用 `-` 或 `_` 连接，层级用 `:` 分隔。
- 标识符优先用业务 ID，避免使用自增主键（不利于跨环境一致性）。
- 避免过深的层级（建议 <= 5 层），便于 `SCAN` 与监控。
- 禁止使用中文或特殊字符，避免客户端兼容性问题。

## 4. 序列化

- Value 序列化：统一使用 **Jackson JSON**，便于跨语言调试与运维直查。
- Key 序列化：纯字符串（`StringRedisSerializer`），不参与序列化框架。
- Spring Boot 配置（`RedisTemplate` 的关键 Bean）：

```java
@Bean
public RedisTemplate<String, Object> redisTemplate(RedisConnectionFactory factory) {
    RedisTemplate<String, Object> template = new RedisTemplate<>();
    template.setConnectionFactory(factory);
    template.setKeySerializer(new StringRedisSerializer());
    template.setHashKeySerializer(new StringRedisSerializer());
    Jackson2JsonRedisSerializer<Object> json = new Jackson2JsonRedisSerializer<>(Object.class);
    ObjectMapper om = new ObjectMapper();
    om.registerModule(new JavaTimeModule());
    om.disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);
    om.activateDefaultTyping(om.getPolymorphicTypeValidator(), ObjectMapper.DefaultTyping.NON_FINAL);
    json.setObjectMapper(om);
    template.setValueSerializer(json);
    template.setHashValueSerializer(json);
    template.afterPropertiesSet();
    return template;
}
```

> 注意：开启 `DefaultTyping` 便于反序列化为具体类型，但存在反序列化漏洞风险，生产环境需限制可信任包名（`activateDefaultTyping` 的 `PolymorphicTypeValidator`）。

## 5. 连接配置

- Redis 版本：7.2.x
- 客户端：Lettuce（Spring Boot 默认）
- 连接池：

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

连接池参数：`max-active=16`（上限，按并发估算）、`max-idle=8`、`min-idle=2`（避免冷启动）、`max-wait=2000ms`（池满时最长等待，超时抛异常）。

## 6. 缓存穿透防护

**穿透**：查询不存在的数据，缓存与 DB 均无，每次请求直达 DB。

防护措施：对不存在的 Key 设置**空值缓存**。

```java
public RealtimeData getRealtime(String ghId) {
    String key = "data:realtime:" + ghId;
    Object val = redisTemplate.opsForValue().get(key);
    if (val != null) {
        return val.equals(EMPTY_FLAG) ? null : (RealtimeData) val;
    }
    RealtimeData data = tdengineMapper.queryLatest(ghId);
    Duration ttl = (data == null) ? Duration.ofSeconds(30) : Duration.ofSeconds(10);
    Object cacheVal = (data == null) ? EMPTY_FLAG : data;
    redisTemplate.opsForValue().set(key, cacheVal, ttl);
    return data;
}
```

- 空值 TTL：30 秒（短于正常数据 TTL），避免空值长期占用内存。
- 空值标记：统一常量 `"__NULL__"`，避免与业务数据混淆。

## 7. 缓存雪崩与击穿

- **雪崩**：大量 Key 同时过期，请求全部回源。防护：
  - TTL 加随机抖动：`TTL = base + random(0, 30s)`，打散过期时间。
  - 热点 Key 永不过期，由后台任务主动刷新。
- **击穿**：单个热点 Key 过期瞬间，大量请求并发回源。防护：
  - 互斥锁（`SET NX EX`），仅允许一个线程回源 DB，其它线程等待重试缓存。
  - 逻辑过期：Value 内嵌过期时间，后台异步刷新，用户始终读到旧数据。

## 8. 监控指标

通过 `redis_exporter` 暴露 Prometheus 指标，重点关注：内存使用率（`redis_memory_used/redis_memory_max` > 80% 需扩容）、连接数（`redis_connected_clients` 异常增长排查泄漏）、命中率（`hits/(hits+misses)` < 70% 说明策略需调整）、慢查询（`redis_slowlog_length` > 0 排查大 Key）、淘汰 Key（`redis_evicted_keys_total` 持续增长说明容量不足）。

## 9. 运维建议

- 禁用 `KEYS *` 命令，改用 `SCAN`，避免阻塞主线程。
- 大 Key（> 10KB）拆分为 Hash 或 List，避免单次操作耗时。
- 生产环境开启 `maxmemory-policy = allkeys-lru`，内存满时按 LRU 淘汰。
- 定期 `redis-cli --bigkeys` 扫描大 Key，`MEMORY USAGE` 评估单 Key 内存占用。
- 持久化：开启 RDB（每 5 分钟全量）+ AOF（每秒刷盘），兼顾恢复速度与数据安全。
