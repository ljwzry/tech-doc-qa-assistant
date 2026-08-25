# 预警系统设计文档

> 智能温室大棚 IoT 项目 — 实时告警子系统
> 版本：v2.1.0  最后更新：2026-07-12

## 1. 设计目标

预警系统负责对设备上报的温湿度、CO2、土壤水分等指标进行实时规则匹配，在指标越限时通过多渠道触达运营人员，目标端到端**延迟 < 3 秒**（从 MQTT 消息到达 Broker 到通知渠道接收入口）。

## 2. 整体处理流程

```
设备 ──MQTT──> EMQX ──> MqttInboundService(后端)
                              │
                              ▼
                       MessageParser / 数据落 TDengine
                              │
                              ▼ (publish)
                       RabbitMQ: alert.exchange (topic)
                              │ routing key = alert.{gh_id}.{severity}
                              ▼
                       AlertConsumer (5 个并行)
                              │
                              ▼
                       AlertRuleEngine.match(metric, value, ruleSet)
                              │ 命中规则
                              ▼
                       NotificationSender.dispatch(channel, alert)
                              │
                       ┌──────┼──────┐
                       ▼      ▼      ▼
                     邮件  企业微信  短信
```

- **MQTT 入站**：后端通过共享订阅 `greenhouse/+/device/+/data` 接收所有设备数据，单条消息解析耗时 < 5ms。
- **RabbitMQ 投递**：解析后立即发布到 `alert.exchange`，避免规则匹配阻塞 MQTT 消费线程。
- **规则引擎**：AlertRuleEngine 采用 Drools-lite 自实现的内存规则集，按 `greenhouse_id` 分组缓存规则，匹配复杂度 O(1) hash + O(n) 条件比较。
- **通知发送**：异步并行调度，单条通知发送超时 5 秒，失败进入重试队列。

## 3. 预警延迟目标

| 链路段 | 目标 P99 延迟 |
|--------|--------------|
| MQTT 入站到 RabbitMQ 投递 | 200 ms |
| RabbitMQ 路由到消费者 | 500 ms |
| AlertRuleEngine 匹配 | 100 ms |
| NotificationSender 投递 | 1500 ms |
| **端到端合计** | **< 3000 ms** |

## 4. 预警级别

| 级别 | severity | 含义 | 默认通知渠道 |
|------|----------|------|-------------|
| 提示 | `info` | 指标接近阈值边界，需关注 | 邮件 |
| 警告 | `warning` | 指标越限，需人工介入 | 邮件 + 企业微信 |
| 紧急 | `critical` | 严重影响作物安全，需立即处置 | 邮件 + 企业微信 + 短信 |

## 5. 预警规则配置

规则存储于 MySQL `alert_rule` 表，由后台管理界面维护，规则变更后通过 Redis Pub/Sub 通知所有 AlertRuleEngine 实例热更新。

表结构关键字段：

```sql
CREATE TABLE alert_rule (
  id           BIGINT PRIMARY KEY AUTO_INCREMENT,
  greenhouse_id VARCHAR(32) NOT NULL,
  device_id    VARCHAR(64),
  metric       VARCHAR(32) NOT NULL COMMENT '指标: temperature/humidity/co2/soil_moisture/light',
  condition_type ENUM('gt','lt','gte','lte','between') NOT NULL,
  threshold_value   DECIMAL(10,2) NOT NULL,
  threshold_upper   DECIMAL(10,2) COMMENT 'between 时上界',
  severity     ENUM('info','warning','critical') NOT NULL,
  duration_sec INT DEFAULT 0 COMMENT '持续越限时长门槛，0=立即触发',
  enabled      TINYINT DEFAULT 1,
  created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_greenhouse (greenhouse_id, enabled)
);
```

规则示例：

| greenhouse_id | metric | condition_type | threshold_value | severity | 说明 |
|---------------|--------|----------------|-----------------|----------|------|
| gh_001 | temperature | gt | 35.0 | critical | 高温保护 |
| gh_001 | temperature | lt | 5.0  | critical | 低温冻害 |
| gh_001 | humidity | between | 30,90 | warning | 湿度越界 |
| gh_001 | co2 | gt | 1200 | warning | CO2 超标 |
| gh_001 | soil_moisture | lt | 0.20 | warning | 土壤过干 |

`duration_sec > 0` 时，需指标在连续 N 秒内均满足条件才触发，避免瞬时抖动误报。

## 6. 通知渠道

### 6.1 邮件（SMTP）

- 协议：SMTP over TLS，端口 587
- 配置项：`spring.mail.host=smtp.greenhouse.local`、`spring.mail.username=alert@greenhouse.local`
- 模板：Freemarker 渲染，主题格式 `[温室告警][{severity}] {greenhouse_id} - {metric} {condition} {threshold}`
- 重试：3 次，间隔 10/30/60 秒

### 6.2 企业微信 Webhook

- 入口：群机器人 Webhook URL，按 `greenhouse_id` 配置不同群
- 消息类型：Markdown，支持 @ 指定成员（critical 级别 @ 全员）
- 频率限制：企业微信单机器人 20 条/分钟，本地令牌桶限速

### 6.3 短信

- 供应商：阿里云短信服务
- 模板：`SMS_GREENHOUSE_ALERT`，变量包含 `{greenhouse_id}`、`{metric}`、`{value}`、`{severity}`
- 触发条件：仅 `critical` 级别，且同一接收人 5 分钟内最多 1 条

## 7. 通知去重

为防止指标持续越限导致告警风暴，采用**滑动窗口去重**：

- 去重 Key：`alert:dedup:{rule_id}:{device_id}`
- 窗口：5 分钟（300 秒）
- 实现：Redis `SET key 1 EX 300 NX`，仅当设置成功才发送通知
- 窗口内重复触发仅累加计数到 `alert:dedup:count:{rule_id}:{device_id}`，供运营人员查看频次

## 8. 预警恢复通知

当某指标从越限状态回到正常范围后，系统自动发送**恢复通知**：

- 维护内存中的"告警活跃集合" `activeAlerts`，key = `{rule_id}:{device_id}`
- 规则匹配时若发现原活跃告警对应的指标已不满足条件，则：
  1. 从 `activeAlerts` 移除
  2. 发布 `recovered` 类型告警到 RabbitMQ
  3. NotificationSender 走与告警相同渠道下发恢复消息，主题前缀 `[恢复]`
- 恢复通知同样走 5 分钟去重窗口，避免抖动场景反复发送。

## 9. RabbitMQ 交换机配置

- 交换机：`alert.exchange`，类型 `topic`，durable=true
- Routing Key 格式：`alert.{greenhouse_id}.{severity}`
  - 示例：`alert.gh_001.critical`、`alert.gh_001.warning`
- 队列：`alert.queue.{greenhouse_id}`，按温室分队列，便于按租户隔离流量
- 绑定：`alert.queue.#` <- `alert.#`（管理后台订阅所有），各温室队列用 `alert.{gh_id}.*` 绑定
- DLX：`alert.dlx.exchange`，死信队列 `alert.dlq`，重试 3 次失败的消息转入死信
- 消息持久化：`delivery-mode=2`，与服务器重启解耦

## 10. 监控与可观测

- 指标暴露：Micrometer + Prometheus
  - `alert_match_total{rule_id,severity}`
  - `alert_dispatch_duration_seconds{channel}`
  - `alert_dedup_skipped_total`
- 告警自监控：预警系统自身故障（如 RabbitMQ 不可达）通过独立心跳上报到运维平台，避免业务告警链路被掩盖
- 日志：所有告警事件落 MySQL `alert_log` 表，保留 90 天，供审计与回溯
