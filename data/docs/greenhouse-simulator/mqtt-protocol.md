# MQTT 协议接入规范

> 适用于智能温室大棚 IoT 项目，定义边缘设备与云端 Broker 之间的通信契约。
> 版本：v2.1.0  最后更新：2026-07-15

## 1. 协议选型

本项目采用 **MQTT v3.1.1** 协议作为设备接入协议，选型理由如下：

- **轻量级**：固定报头最小仅 2 字节，适合 NB-IoT / 4G 等低带宽场景，温室节点普遍采用 Cat.1 模组。
- **QoS 分级**：支持 0 / 1 / 2 三种消息质量等级，可按业务语义区分上报与下发可靠性。
- **遗嘱消息（LWT）**：设备异常断线时 Broker 自动发布遗嘱，便于后端实时感知掉线设备。
- **长连接复用**：单 TCP 连接承载双向通信，避免频繁建链消耗模组功耗。
- **生态成熟**：EMQX 5.x 提供完整的规则引擎、认证、共享订阅支持，与 Spring Boot 集成成本极低。

> 暂不采用 MQTT 5.0 的原因：当前主流模组（如 EC600S、Air724UG）固件仍以 v3.1.1 为主，5.0 的 Session Expiry、Shared Subscription 标准化等特性在 v2.x 阶段非必需。

## 2. 连接参数

| 参数 | 取值 | 说明 |
|------|------|------|
| Broker 地址 | `tcp://emqx.greenhouse.local:1883` | 内网域名，TLS 端口 8883 |
| ClientID | `gh_{greenhouse_id}_{device_id}` | 全局唯一，下划线分隔 |
| Username | `{device_id}` | 设备唯一标识 |
| Password | 设备密钥 + 时间戳的 HMAC-SHA256 | 生产环境启用 |
| Keep Alive | 60 秒 | 心跳周期，1.5 倍超时判定掉线 |
| Clean Session | `true` | 不保留历史会话，避免订阅堆积 |
| Protocol Level | 4 | MQTT v3.1.1 |
| Connect Timeout | 10 秒 | 建链超时 |

## 3. Topic 命名规范

采用分层命名，层级之间用 `/` 分隔，便于 EMQX 权限树匹配与共享订阅：

```
greenhouse/{greenhouse_id}/device/{device_id}/data       # 设备数据上报（上行）
greenhouse/{greenhouse_id}/device/{device_id}/status     # 设备在线状态变更（上行）
greenhouse/{greenhouse_id}/device/{device_id}/response   # 平台下发指令的回执（上行）
greenhouse/{greenhouse_id}/device/{device_id}/command    # 平台下发指令（下行）
```

- `greenhouse_id` 形如 `gh_001`，`device_id` 形如 `dev_temp_001`。
- 后端订阅通配符：`greenhouse/+/device/+/data`、`greenhouse/+/device/+/status`。
- 设备仅订阅自身 command Topic，避免越权接收其它设备指令。

## 4. QoS 要求

| 业务方向 | QoS | 理由 |
|----------|-----|------|
| 设备数据上报（data） | 1 | 至少一次送达，允许少量重复，后端按 `device_id + timestamp` 幂等去重 |
| 设备状态变更（status） | 1 | 在线/离线事件需可靠送达，但容忍极小概率重复 |
| 平台指令下发（command） | 2 | 恰好一次，避免重复下发 `reboot`、`irrigate` 等有副作用指令 |
| 指令回执（response） | 1 | 设备回报执行结果，平台缺失回执时通过重试机制兜底 |
| 遗嘱消息（LWT） | 1 | 设备掉线广播，需保证触达 |

## 5. 数据上报 JSON 格式

Topic：`greenhouse/{greenhouse_id}/device/{device_id}/data`

```json
{
  "device_id": "dev_temp_001",
  "greenhouse_id": "gh_001",
  "timestamp": 1720605600000,
  "seq": 20260715001,
  "data": {
    "temperature": 26.8,
    "humidity": 68.2,
    "light": 18500,
    "co2": 620,
    "soil_moisture": 0.42
  }
}
```

字段说明：
- `timestamp`：毫秒级 Unix 时间戳，设备本地时钟需与 NTP 同步，偏差不超过 5 秒。
- `seq`：单调递增序号，用于乱序检测与重复过滤。
- 数值字段保留 1 位小数（light、co2 为整数），缺失字段允许省略但禁止置 `null`。

## 6. 指令下发 JSON 格式

Topic：`greenhouse/{greenhouse_id}/device/{device_id}/command`

```json
{
  "command_id": "cmd_20260715_0001",
  "command_type": "irrigate",
  "params": {
    "duration_sec": 120,
    "valve_id": "v_01"
  },
  "timeout_sec": 30,
  "issued_by": "scheduler"
}
```

支持的 `command_type`：`reboot`、`irrigate`、`vent_open`、`vent_close`、`light_on`、`light_off`、`set_threshold`。设备收到指令后须在 `timeout_sec` 内回填 `response`：

```json
{
  "command_id": "cmd_20260715_0001",
  "code": 0,
  "message": "ok",
  "timestamp": 1720605612000
}
```

`code=0` 表示成功，非 0 表示失败，`message` 描述失败原因。

## 7. 断线重连策略

设备采用**指数退避 + 抖动**策略，避免大量设备同时重连造成惊群：

- 初始间隔：5 秒
- 最大间隔：60 秒
- 退避系数：1.8
- 抖动：±15% 随机
- 重连次数上限：无限（持续尝试直至成功）
- 每次重连前先检查 NTP 时间，避免证书校验失败

伪代码：
```java
long delay = 5000;
while (!connected) {
    try { connect(); }
    catch (Exception e) {
        delay = Math.min(60000, (long)(delay * 1.8 * (0.85 + rand*0.3)));
        Thread.sleep(delay);
    }
}
```

## 8. 频率限制

- 单设备数据上报**最大 1 条/秒**，超出由 EMQX 限流丢弃并记录指标。
- 推荐采样周期 30 秒（温湿度）至 60 秒（CO2、土壤水分），变化阈值触发即时上报。
- 后端侧通过 Redis 令牌桶对 command 下发限速：单设备 10 条/分钟。

## 9. 遗嘱消息配置

设备连接时注册 LWT，Topic 为 `greenhouse/{greenhouse_id}/device/{device_id}/status`，payload：

```json
{
  "device_id": "dev_temp_001",
  "online": false,
  "reason": "connection_lost",
  "timestamp": 0
}
```

`timestamp` 由 Broker 在遗嘱触发时填充。设备正常上线后需主动发布一条 `online=true` 的状态消息，覆盖遗嘱影响，避免历史掉线标记残留。

## 10. 安全建议

- 生产环境关闭 EMQX 匿名访问，启用基于设备证书的双向 TLS（端口 8883）。
- Username/Password 走 HMAC-SHA256，密钥下发通过设备出厂烧录平台，禁止明文存盘。
- EMQX ACL 规则限定设备只能 PUB 自身 data/status/response Topic，SUB 自身 command Topic。
- 后端消费端与 Broker 之间通过内网直连，不经过公网。
