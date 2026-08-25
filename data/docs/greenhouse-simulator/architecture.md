# 智能温室大棚监控系统 — 架构设计文档

> **版本**：v2.1
> **作者**：后端开发组
> **最后更新**：2026-07-15

---

## 1. 系统概述

智能温室大棚监控系统是一个基于 Spring Boot + TDengine + MQTT 的物联网数据采集与监控平台。系统通过部署在温室内部的传感器节点采集环境数据（温度、湿度、光照、CO2浓度、土壤湿度），通过 MQTT 协议上报至后端服务，后端将数据存储至 TDengine 时序数据库，并提供 REST API 供前端大屏和移动端查询。

### 1.1 系统边界

```
[传感器节点] --MQTT--> [EMQX Broker] --WebSocket--> [Spring Boot 后端] --JDBC--> [TDengine]
                                                                                  |
                                                                                  +--REST API--> [前端大屏 / 移动端]
                                                                                  +--AMQP--> [RabbitMQ] --> [预警服务]
```

### 1.2 核心设计原则

1. **高吞吐写入**：采用 TDengine 时序数据库，单节点写入吞吐量 > 10,000 条/秒
2. **低延迟告警**：通过 RabbitMQ 异步解耦，告警延迟 < 3 秒
3. **水平扩展**：Spring Boot 无状态设计，可通过 K8s 水平扩容
4. **协议标准化**：设备侧统一采用 MQTT v3.1.1 协议，Topic 规范化管理

---

## 2. 技术架构

### 2.1 技术栈

| 层级 | 技术选型 | 版本 | 说明 |
|------|---------|------|------|
| 设备通信 | MQTT | v3.1.1 | 通过 EMQX Broker 中转 |
| 消息代理 | EMQX | 5.x | 开源 MQTT Broker，支持 100 万并发连接 |
| 后端框架 | Spring Boot | 3.2.0 | Java 17，基于 Spring Boot 3.x |
| 时序数据库 | TDengine | 3.0 | 存储传感器时序数据 |
| 关系型数据库 | MySQL | 8.0 | 存储设备信息、用户信息、告警规则 |
| 消息队列 | RabbitMQ | 3.12 | 异步告警通知 |
| 缓存 | Redis | 7.2 | 设备在线状态缓存 |
| 连接池 | HikariCP | 5.0 | 数据库连接池管理 |

### 2.2 模块划分

```
greenhouse-service/
├── greenhouse-gateway/        # MQTT 消息接入层
│   ├── MqttMessageListener     # MQTT 消息监听器
│   └── MessageParser            # 消息解析与校验
├── greenhouse-core/            # 核心业务逻辑
│   ├── device/                  # 设备管理
│   ├── alert/                   # 预警规则引擎
│   └── data/                    # 数据查询服务
├── greenhouse-persistence/     # 数据持久化层
│   ├── tdengine/                # TDengine 写入与查询
│   └── mysql/                   # MySQL CRUD
├── greenhouse-api/              # REST API 层
│   ├── DataController           # 数据查询接口
│   ├── DeviceController         # 设备管理接口
│   └── AlertController          # 预警管理接口
└── greenhouse-alert/            # 预警通知服务
    ├── AlertRuleEngine          # 规则匹配引擎
    └── NotificationSender       # 多渠道通知
```

---

## 3. 数据库设计

### 3.1 TDengine 超级表设计

```sql
-- 传感器数据超级表
CREATE STABLE IF NOT EXISTS sensor_data (
    ts            TIMESTAMP,       -- 采集时间戳
    temperature   FLOAT,           -- 温度（℃）
    humidity      FLOAT,           -- 空气湿度（%）
    light         FLOAT,           -- 光照强度（Lux）
    co2           FLOAT,           -- CO2浓度（ppm）
    soil_moisture FLOAT            -- 土壤湿度（%）
) TAGS (
    device_id     NCHAR(32),       -- 设备ID
    greenhouse_id NCHAR(32),       -- 温室ID
    location      NCHAR(64)        -- 传感器安装位置
);
```

### 3.2 MySQL 核心表

```sql
-- 预警规则表
CREATE TABLE alert_rule (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    rule_name       VARCHAR(128) NOT NULL COMMENT '规则名称',
    greenhouse_id   VARCHAR(32) NOT NULL COMMENT '关联温室',
    metric          VARCHAR(32) NOT NULL COMMENT '监控指标: temperature/humidity/co2等',
    condition_type  VARCHAR(16) NOT NULL COMMENT '条件类型: gt/lt/gte/lte/between',
    threshold_value VARCHAR(64) NOT NULL COMMENT '阈值',
    severity        VARCHAR(16) DEFAULT 'warning' COMMENT '级别: info/warning/critical',
    enabled         TINYINT DEFAULT 1 COMMENT '是否启用',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## 4. MQTT Topic 规范

### 4.1 Topic 命名规则

```
greenhouse/{greenhouse_id}/device/{device_id}/data     -- 设备数据上报
greenhouse/{greenhouse_id}/device/{device_id}/status   -- 设备状态变更
greenhouse/{greenhouse_id}/device/{device_id}/response -- 服务端下行响应
greenhouse/{greenhouse_id}/command/{command_id}        -- 指令下发
```

### 4.2 数据上报消息格式

```json
{
  "device_id": "sensor001",
  "timestamp": 1721001600000,
  "data": {
    "temperature": 25.6,
    "humidity": 68.2,
    "light": 12500,
    "co2": 420,
    "soil_moisture": 45.3
  }
}
```

---

## 5. 部署架构

### 5.1 开发环境

| 组件 | 地址 | 端口 |
|------|------|------|
| Spring Boot 后端 | localhost | 8080 |
| EMQX Broker | localhost | 1883 (MQTT) / 8083 (WebSocket) |
| TDengine | localhost | 6030 |
| MySQL | localhost | 3306 |
| Redis | localhost | 6379 |
| RabbitMQ | localhost | 5672 / 15672 (管理界面) |

### 5.2 生产环境建议

- Spring Boot：2 核 4G 起步，建议 4 核 8G
- EMQX：4 核 8G，最大连接数 50 万
- TDengine：8 核 16G，SSD 存储，数据保留策略 365 天
- MySQL：4 核 8G，200GB SSD
