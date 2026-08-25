# TDengine 使用指南

> 适用于智能温室大棚 IoT 项目时序数据存储场景
> 版本：TDengine 3.0.x  最后更新：2026-07-13

## 1. 概述

TDengine 是一款高性能、分布式的时序数据库（Time-Series Database），专为物联网、工业互联网场景设计，原生支持 SQL 语法。主要特点：单机百万级 TPS 写入、列式存储 + 时间分区；典型压缩比 10~50 倍；每个子表最新数据自动缓存于内存；支持 Vnode 分片 + 副本水平扩展；兼容大部分 MySQL 语法，JDBC/ORM 集成成熟。

## 2. 超级表与子表

TDengine 引入"超级表（STABLE）+ 子表"的两层模型，是理解其数据组织的关键：

- **超级表（STABLE）**：表结构模板，定义所有子表共享的列（时间戳 + 指标列）与静态标签（TAG）。本身不直接存储数据，仅作为建表与查询的"类型"。
- **子表**：实际存储数据的物理表，每张子表对应一个具体数据源（如一台设备），继承超级表的列结构并通过 TAG 值区分身份（如 `device_id`、`greenhouse_id`）。
- 类比关系型数据库：超级表 ≈ 表结构定义 + 视图，子表 ≈ 分区表/分表，TAG ≈ 分区键/索引列。

## 3. 建表语法

```sql
-- 创建数据库
CREATE DATABASE greenhouse
  KEEP 365
  DURATION 10
  BUFFER 16
  PAGES 256;

USE greenhouse;

-- 创建超级表
CREATE STABLE gh_data (
  ts TIMESTAMP,
  temperature FLOAT,
  humidity FLOAT,
  light INT,
  co2 INT,
  soil_moisture FLOAT
) TAGS (
  greenhouse_id BINARY(32),
  device_id BINARY(64),
  device_type BINARY(16)
);

-- 基于超级表创建子表
CREATE TABLE dev_temp_001 USING gh_data
  TAGS ('gh_001', 'dev_temp_001', 'temperature');
```

要点：
- 第一列必须为 `TIMESTAMP` 类型，命名习惯为 `ts`。
- `TAGS` 为静态属性，不随时间变化，存储于元数据，查询时按 TAG 过滤可大幅减少扫描量。
- 子表名建议与 `device_id` 一致，便于运维定位。

## 4. 查询语法

### 4.1 基础查询

```sql
-- 查询单设备最近 1 小时数据
SELECT ts, temperature, humidity
FROM dev_temp_001
WHERE ts >= NOW - 1h
ORDER BY ts ASC;

-- 按超级表 + TAG 过滤查询
SELECT ts, temperature
FROM gh_data
WHERE greenhouse_id = 'gh_001'
  AND ts >= NOW - 1h;
```

### 4.2 时间窗口聚合

```sql
-- 按小时聚合温度均值
SELECT AVG(temperature), MAX(temperature), MIN(temperature)
FROM gh_data
WHERE greenhouse_id = 'gh_001'
  AND ts >= NOW - 1d
INTERVAL(1h);

-- 按天聚合
SELECT AVG(temperature) AS avg_temp
FROM gh_data
WHERE greenhouse_id = 'gh_001'
  AND ts >= NOW - 7d
INTERVAL(1d)
FILL(VALUE, 0);
```

`INTERVAL` 支持的时间单位：`1s`、`1m`、`1h`、`1d`、`1w`、`1n`、`1y`。`FILL` 用于补齐无数据的窗口，`VALUE, 0` 表示用 0 填充。

### 4.3 跨子表分组聚合

```sql
-- 各设备最近温度均值
SELECT device_id, AVG(temperature) FROM gh_data
WHERE ts >= NOW - 1h GROUP BY device_id;

-- 各温室温度均值
SELECT greenhouse_id, AVG(temperature) FROM gh_data
WHERE ts >= NOW - 1h GROUP BY greenhouse_id;
```

## 5. 常用聚合函数

| 函数 | 含义 | 示例 |
|------|------|------|
| `AVG(col)` | 平均值 | `AVG(temperature)` |
| `MAX(col)` / `MIN(col)` | 最大/最小值 | `MAX(co2)` / `MIN(soil_moisture)` |
| `COUNT(col)` | 计数 | `COUNT(temperature)` |
| `LAST(col)` / `FIRST(col)` | 最新/首条值 | `LAST(temperature)` |
| `SUM(col)` / `STDDEV(col)` | 求和/标准差 | `SUM(light)` |
| `PERCENTILE(col, 95)` | 分位数 | `PERCENTILE(temperature, 95)` |
| `TWA(col)` | 时间加权平均 | `TWA(temperature)` |

`LAST` 在不指定时间范围时返回子表最新一条，TDengine 会走缓存，性能极高，常用于实时大屏。

## 6. 数据保留策略

建库时通过两个参数控制：`KEEP 365`（数据保留 365 天，超期自动删除）、`DURATION 10`（每 10 天一个数据文件块，便于按时间分片压缩与查询）。调整示例：`ALTER DATABASE greenhouse KEEP 730;`（保留期改 2 年）、`ALTER DATABASE greenhouse DURATION 30;`（文件块改 30 天）。注意 `DURATION` 调整只影响新写入数据，历史文件不会重新切分。

## 7. 性能优化建议

### 7.1 批量写入

单条插入与批量插入性能差距可达 **10 倍**以上，强烈推荐批量写入：

```sql
-- 不推荐：单条插入
INSERT INTO dev_temp_001 VALUES (NOW, 26.8, 68.2, 18500, 620, 0.42);

-- 推荐：多行批量插入
INSERT INTO dev_temp_001 VALUES
  (NOW-10s, 26.5, 68.0, 18400, 615, 0.42),
  (NOW-5s,  26.7, 68.1, 18500, 618, 0.42),
  (NOW,     26.8, 68.2, 18500, 620, 0.42);
```

JDBC 端建议使用 `addBatch` + `executeBatch`，单批次 1000~5000 行。

### 7.2 写入频率

- 每个子表写入频率**建议不低于 1 次/秒**，低于此频率会触发 TDengine 内部合并，影响性能。
- 高频采集场景可在边缘网关侧聚合后再上报（如 1 秒聚合一次）。

### 7.3 查询带上时间范围

```sql
-- 不推荐：全表扫描
SELECT * FROM gh_data WHERE greenhouse_id = 'gh_001';

-- 推荐：限定时间范围
SELECT * FROM gh_data
WHERE greenhouse_id = 'gh_001'
  AND ts >= NOW - 1d
  AND ts < NOW;
```

TDengine 按时间分区存储，时间范围命中分区可跳过大量文件扫描，是性能优化的第一原则。

### 7.4 其它建议

- 查询优先按 TAG 过滤（`greenhouse_id`、`device_id`），再叠加时间范围，避免 `SELECT *`。
- 大范围聚合查询走缓存层（Redis），避免直接打 TDengine。
- 单 Vnode 子表数建议 < 10 万，否则元数据膨胀影响建表与查询规划。
- TAG 类型优先用 `BINARY` 定长，避免 `NCHAR` 带来的编码开销；避免频繁 `ALTER STABLE` 修改列结构。

## 8. JDBC 驱动与连接串

Maven 依赖：

```xml
<dependency>
  <groupId>com.taosdata.jdbc</groupId>
  <artifactId>taos-jdbcdriver</artifactId>
  <version>3.0.3</version>
</dependency>
```

驱动类：`Class.forName("com.taosdata.jdbc.TSDBDriver");`

> TDengine 3.x 同时提供原生连接（`TSDBDriver`）与 REST 连接（`RestfulDriver`）。原生连接性能更优，但要求应用所在机器部署 taos 客户端；REST 连接无需客户端，跨平台更友好，性能略低。

原生连接串：
```
jdbc:TAOS://localhost:6030/greenhouse?charset=UTF-8&timezone=Asia/Shanghai
```

REST 连接串（端口 6041，需在 `taosadapter` 中开启）：
```
jdbc:TAOS-RS://localhost:6041/greenhouse?charset=UTF-8
```

参数说明：`localhost:6030` 为服务地址与原生端口，`/greenhouse` 为数据库名，`charset=UTF-8` 与建库保持一致。

## 9. 常见问题

- **写入报错 "Table does not exist"**：子表未创建，建议采用"自动建表"语法 `INSERT INTO dev_temp_001 USING gh_data TAGS(...) VALUES(...)`，写入时自动建子表。
- **查询慢**：90% 是未带时间范围或 TAG 过滤，先检查 SQL。
- **连接串报 "Unable to establish connection"**：检查 `taos.cfg` 中 `firstEp` 与防火墙 6030/6041 端口。
- **时区错误**：连接串加 `timezone=Asia/Shanghai`，避免 `NOW()` 与本地时间偏差。
