# RabbitMQ 使用说明

> 适用于智能温室大棚 IoT 项目异步告警通知场景
> 版本：RabbitMQ 3.12.x  最后更新：2026-07-11

## 1. 概述

RabbitMQ 是基于 AMQP 0-9-1 协议的开源消息中间件，提供可靠的消息路由、确认、持久化与高可用集群能力。本项目使用 RabbitMQ 作为**异步告警通知**的传输通道，将告警生成与通知发送解耦，提升系统吞吐与稳定性。

核心概念：
- **Producer**：消息生产者，本项目为后端 AlertPublisher。
- **Exchange**：交换机，接收生产者消息并按规则路由到队列。
- **Queue**：队列，存储消息直到消费者处理。
- **Binding**：交换机与队列之间的绑定关系，附带 routing key。
- **Consumer**：消息消费者，本项目为 AlertConsumer。

## 2. 交换机类型选择

RabbitMQ 提供四种交换机类型，本项目按需选用。

### 2.1 Direct（直连）

- 路由规则：routing key **完全相等**才路由到对应队列。
- 适用场景：点对点精确路由，如任务分发、订单处理。
- 示例：routing key = `alert.gh_001.critical` 仅匹配 binding key 为 `alert.gh_001.critical` 的队列。

### 2.2 Topic（主题，本项目使用）

- 路由规则：routing key 按**模式匹配** binding key，支持通配符：
  - `*`：匹配一个单词
  - `#`：匹配零个或多个单词
- 适用场景：按业务维度灵活路由，支持批量订阅。
- 本项目选择理由：告警需按 `greenhouse_id` 与 `severity` 两个维度分发，topic 类型可灵活匹配。
  - `alert.gh_001.critical` -> 队列1（gh_001 全量）
  - `alert.gh_001.*` -> 队列2（gh_001 所有级别）
  - `alert.*.critical` -> 队列3（所有温室的紧急告警）

### 2.3 Fanout（广播）

- 路由规则：忽略 routing key，消息广播到所有绑定队列。
- 适用场景：配置下发、日志广播。
- 本项目未使用。

### 2.4 Headers

- 路由规则：基于消息头属性匹配，忽略 routing key。
- 适用场景：复杂多条件路由，本项目未使用。

## 3. 本项目配置

### 3.1 交换机

- 名称：`alert.exchange`
- 类型：`topic`
- durable：`true`（持久化，Broker 重启不丢失）
- auto-delete：`false`

### 3.2 Routing Key 格式

```
alert.{greenhouse_id}.{severity}
```

- `greenhouse_id`：温室编号，如 `gh_001`、`gh_002`
- `severity`：告警级别，取值 `info` / `warning` / `critical`

示例：
```
alert.gh_001.critical
alert.gh_002.warning
alert.gh_003.info
```

### 3.3 队列命名

```
alert.queue.{greenhouse_id}
```

按温室分队列，便于按租户隔离流量与并发控制。每个队列绑定到 `alert.exchange`，binding key 为 `alert.{greenhouse_id}.*`。

| 队列 | Binding Key | 说明 |
|------|-------------|------|
| `alert.queue.gh_001` | `alert.gh_001.*` | gh_001 所有告警 |
| `alert.queue.gh_002` | `alert.gh_002.*` | gh_002 所有告警 |
| `alert.queue.all_critical` | `alert.*.critical` | 所有温室紧急告警（运维监控用） |

### 3.4 队列属性

- durable：`true`（持久化队列）
- auto-delete：`false`
- arguments：
  - `x-message-ttl: 86400000`（消息 TTL 24 小时，超时进死信）
  - `x-dead-letter-exchange: alert.dlx.exchange`
  - `x-dead-letter-routing-key: alert.dlq`

## 4. 消费者配置

### 4.1 关键参数

| 参数 | 取值 | 说明 |
|------|------|------|
| acknowledge-mode | `manual` | 手动确认，业务成功后 `basicAck`，失败 `basicNack` |
| prefetch | `10` | 每个消费者最多同时处理 10 条未确认消息 |
| concurrency | `5` | 当前消费者数量（线程数） |
| max-concurrency | `10` | 最大消费者数量，根据积压动态扩容 |
| retry.max-attempts | `3` | 单条消息重试上限 |
| retry.initial-interval | `1000ms` | 首次重试间隔 |
| retry.multiplier | `2.0` | 退避倍数，1s -> 2s -> 4s |

### 4.2 消费者数量决策

当前 `concurrency=5`，依据如下：

- 单条告警处理（规则匹配 + 通知发送）平均 1.2 秒。
- 单消费者吞吐：1 / 1.2 ≈ 0.83 条/秒。
- 5 个消费者合计吞吐：4.15 条/秒。
- 业务峰值预估：3 条/秒（1000 设备 × 1% 告警率 / 3 秒窗口）。
- 留 30% 余量，5 个消费者满足需求；峰值超预期时自动扩到 `max-concurrency=10`。

### 4.3 手动 ACK 示例

```java
@RabbitListener(queues = "alert.queue.gh_001", concurrency = "5")
public void onAlert(Message message, Channel channel) throws IOException {
    long tag = message.getMessageProperties().getDeliveryTag();
    try {
        AlertEvent event = parse(message);
        alertRuleEngine.match(event);
        notificationSender.dispatch(event);
        channel.basicAck(tag, false);
    } catch (BusinessException e) {
        // 业务异常，重试有限次数后进死信
        channel.basicNack(tag, false, false);
    } catch (Exception e) {
        // 系统异常，requeue 重试
        channel.basicNack(tag, false, true);
    }
}
```

## 5. 死信队列

消息重试 3 次仍失败，或超过 TTL，进入死信队列：

- 死信交换机：`alert.dlx.exchange`（direct 类型）
- 死信队列：`alert.dlq`
- Routing Key：`alert.dlq`

死信队列消费策略：
- 由独立的 `DeadLetterConsumer` 监听，仅记录日志与落库 `alert_failed_log` 表，供人工排查。
- 不再自动重试，避免毒消息循环。
- 运维每日扫描 `alert_failed_log`，对失败告警人工补发。

## 6. 消息持久化

为保证 Broker 重启后消息不丢失，开启持久化：交换机 `durable=true`、队列 `durable=true`、消息 `delivery-mode=2`（persistent）。

Spring Boot 配置 `spring.rabbitmq.template.delivery-mode=persistent`，或代码层面通过 `message.getMessageProperties().setDeliveryMode(MessageDeliveryMode.PERSISTENT)` 设置。

> 持久化会降低吞吐（约 30%），但 IoT 告警场景对可靠性要求高于性能，权衡可接受。

## 7. 镜像队列与高可用

生产环境部署 RabbitMQ 三节点集群，关键队列开启镜像：

- 策略名称：`ha-alert`
- 模式：`exactly`，副本数 2
- 同步：`automatic`
- 应用范围：`^alert\.`

```bash
rabbitmqctl set_policy ha-alert "^alert\." \
  '{"ha-mode":"exactly","ha-params":2,"ha-sync-mode":"automatic"}'
```

效果：每个 alert 队列在 2 个节点存在副本，单节点宕机不影响消费。

## 8. 监控指标

通过 `rabbitmq_exporter` 暴露 Prometheus 指标，重点关注：

| 指标 | 告警阈值 | 说明 |
|------|----------|------|
| `rabbitmq_queue_messages_ready` | > 100 | 队列就绪消息积压 |
| `rabbitmq_queue_messages_unacknowledged` | > 50 | 未确认消息过多，消费能力不足 |
| `rabbitmq_consumers` | < 5 | 消费者数量异常 |
| `rabbitmq_queue_messages_ready_rate` | 持续 > 10/s | 生产速率远超消费速率 |
| `rabbitmq_node_disk_free` | < 1GB | 磁盘告警，Broker 会阻塞发布 |

## 9. 常见问题

- **消息积压**：先排查消费者是否异常（线程阻塞、第三方接口超时），再考虑临时扩容 `concurrency`。
- **消息重复消费**：消费端做幂等，按 `alert_id` 去重（Redis `SET NX EX`）。
- **消息丢失**：确认生产端开启 publisher confirm，消费端手动 ACK，队列与消息持久化。
- **连接频繁断开**：检查 `heartbeat`（默认 60s），网络抖动场景调到 30s；连接池配置 `spring.rabbitmq.connection-timeout`。
