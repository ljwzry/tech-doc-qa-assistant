# 智能温室大棚监控系统 — API 接口文档

> **版本**：v2.1
> **Base URL**：`http://localhost:8080/api/v1`
> **认证方式**：Bearer Token (JWT)

---

## 1. 传感器数据接口

### 1.1 查询实时数据

**GET** `/data/realtime/{greenhouse_id}`

获取指定温室的最新一条传感器数据。

**路径参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|:----:|------|
| greenhouse_id | string | 是 | 温室ID，如 `gh_001` |

**响应示例**：

```json
{
  "code": 200,
  "data": {
    "greenhouse_id": "gh_001",
    "timestamp": "2026-07-15T10:30:00+08:00",
    "temperature": 25.6,
    "humidity": 68.2,
    "light": 12500,
    "co2": 420,
    "soil_moisture": 45.3
  }
}
```

### 1.2 查询历史数据

**GET** `/data/history/{greenhouse_id}`

**Query 参数**：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|:----:|--------|------|
| metric | string | 是 | - | 指标名：temperature/humidity/light/co2/soil_moisture |
| start | string | 是 | - | 起始时间，ISO 8601 格式 |
| end | string | 是 | - | 结束时间 |
| interval | string | 否 | 1m | 聚合间隔：1m/5m/1h/1d |
| agg | string | 否 | avg | 聚合函数：avg/max/min/last |

**响应示例**：

```json
{
  "code": 200,
  "data": [
    {"ts": "2026-07-15T10:00:00+08:00", "value": 25.2},
    {"ts": "2026-07-15T10:05:00+08:00", "value": 25.4},
    {"ts": "2026-07-15T10:10:00+08:00", "value": 25.6}
  ]
}
```

---

## 2. 设备管理接口

### 2.1 获取设备列表

**GET** `/devices`

**Query 参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|:----:|------|
| greenhouse_id | string | 否 | 按温室ID过滤 |
| device_type | string | 否 | 按设备类型过滤 |
| status | int | 否 | 按状态过滤：0-离线 1-在线 |
| page | int | 否 | 页码，默认 1 |
| size | int | 否 | 每页条数，默认 20 |

### 2.2 获取设备详情

**GET** `/devices/{device_id}`

**响应示例**：

```json
{
  "code": 200,
  "data": {
    "device_id": "sensor001",
    "device_name": "A区温度传感器",
    "greenhouse_id": "gh_001",
    "device_type": "temperature",
    "status": 1,
    "last_online": "2026-07-15T10:30:00+08:00",
    "location": "zone_a"
  }
}
```

---

## 3. 预警管理接口

### 3.1 获取预警规则列表

**GET** `/alerts/rules`

**Query 参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|:----:|------|
| greenhouse_id | string | 否 | 按温室过滤 |
| severity | string | 否 | 按级别过滤：info/warning/critical |
| enabled | int | 否 | 是否启用 |

### 3.2 创建预警规则

**POST** `/alerts/rules`

**请求体**：

```json
{
  "rule_name": "A区高温预警",
  "greenhouse_id": "gh_001",
  "metric": "temperature",
  "condition_type": "gt",
  "threshold_value": "35",
  "severity": "critical"
}
```

### 3.3 查询告警记录

**GET** `/alerts/records`

**Query 参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|:----:|------|
| greenhouse_id | string | 否 | 按温室过滤 |
| severity | string | 否 | 按级别过滤 |
| start | string | 否 | 起始时间 |
| end | string | 否 | 结束时间 |
| page | int | 否 | 页码 |
| size | int | 否 | 每页条数 |

### 3.4 告警统计

**GET** `/alerts/stats/{greenhouse_id}`

**Query 参数**：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|:----:|--------|------|
| period | string | 否 | 24h | 统计周期：1h/6h/24h/7d/30d |

**响应示例**：

```json
{
  "code": 200,
  "data": {
    "total": 156,
    "by_severity": {"critical": 12, "warning": 89, "info": 55},
    "by_metric": {"temperature": 45, "humidity": 32, "co2": 28, "soil_moisture": 51}
  }
}
```

---

## 4. 通用响应格式

所有接口统一返回以下格式：

```json
{
  "code": 200,
  "message": "success",
  "data": {}
}
```

**错误码**：

| code | 说明 |
|------|------|
| 200 | 成功 |
| 400 | 参数错误 |
| 401 | 未认证 |
| 403 | 无权限 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |
