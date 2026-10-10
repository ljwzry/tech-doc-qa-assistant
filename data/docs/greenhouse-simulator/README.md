<p align="center">
  <h1 align="center">冬枣种植智慧大棚物联网平台</h1>
  <h4 align="center">SpringBoot + Vue + nanobot AI Agent — 全栈智慧农业解决方案</h4>
</p>

## 项目简介

冬枣种植智慧大棚物联网平台，集环境监测、数据采集、智能预警与 AI 对话分析于一体。

- **后端**：若依框架 (RuoYi-Vue v3.9.2) 二次开发 — Spring Boot 4.x + MyBatis + PostgreSQL + TDengine
- **AI 胶水层**：Gateway（SSE 聊天代理） + MCP Server（35 个物联网工具） + MQTT Bridge（传感器数据注入）
- **AI Agent**：nanobot — MCP tool-calling + 多轮对话 + SSE 流式输出，从仓库源码直接构建
- **知识图谱**：冬枣种植病虫害 / 物候期 / 药剂结构化知识 + Neo4j 图查询
- **前端**：Vue 2.x + Element UI（由前端团队本地构建，服务器不负责前端构建）

## 项目结构

```
dongzao/
├── backend/                     # Java 全套
│   ├── ruoyi-admin/             # Spring Boot 入口 (port 17001)
│   ├── ruoyi-common/            # 公共模块
│   ├── ruoyi-framework/         # 安全框架 (JWT + Redis)
│   ├── ruoyi-generator/         # 代码生成器
│   ├── ruoyi-iot/               # IoT 业务 (14 controllers, ~83 endpoints)
│   ├── ruoyi-quartz/            # 定时任务
│   ├── ruoyi-system/            # 系统管理 (用户/角色/菜单)
│   └── ruoyi-ui/                # Vue 2.x 前端
├── services/                    # Python 胶水层
│   ├── gateway/                 # Gateway (port 17003) — JWT auth, SSE 代理, WebSocket 推送, 定时任务
│   ├── mcp-server/              # MCP Server (port 17004) — 35 MCP tools, 6 层参数校验, 知识图谱查询
│   └── mqtt-bridge/             # MQTT Bridge — 订阅传感器数据, AI 分析, 注入 Gateway 推送
├── tools/                       # 辅助工具
│   ├── crawler/                 # 知识爬虫 — 4 站点采集, LLM 实体抽取, JSON/Neo4j 输出
│   └── simulator/               # 温室传感器数据模拟器
├── deploy/                      # 部署配置
│   ├── deploy.sh                # 全栈一键部署脚本 (交互式)
│   ├── docker-compose-full.yml  # 应用层 (backend + nanobot + glue + UI)
│   ├── docker-compose.glue.yml  # 仅胶水层
│   ├── mosquitto.conf
│   └── nginx.conf
├── sql/                         # 数据库初始化
├── docs/                        # 技术文档
├── nanobot-main/                # nanobot AI Agent（纳入仓库，部署时从源码构建）
├── docker-compose.yml           # 基础设施 (PostgreSQL + Valkey + TDengine + Mosquitto + Neo4j)
└── pom.xml                      # Maven 父 POM
```

## 架构总览

```
浏览器 (:17000) ──→ Nginx ──┬── /prod-api/* ──→ Java Backend (:17001)
                            │                        │
                            └── /api/chat ──→ Gateway (:17003) ──→ nanobot (:17002)
                                                     │                │
                            ┌────────────────────────┘                │
                            │                                  MCP Protocol
                            ▼                                         │
                     MCP Server (:17004) ←────────────────────────────┘
                            │
                     ┌──────┼──────┐
                     ▼      ▼      ▼
                  Backend  Redis  Neo4j
                    :8080  :6379  :7687

  MQTT 传感器 ──→ Mosquitto (:17013) ──→ MQTT Bridge ──→ nanobot ──→ Gateway ──→ WS 推送
```

| 层 | 组件 | 默认端口 | 说明 |
|----|------|---------|------|
| 前端 | Nginx + Vue | **17000** | 前端团队本地构建，dist/ 已存在则自动部署 |
| 后端 | Java Spring Boot | **17001** | REST API, JWT HS512 鉴权, 数据持久化 |
| AI | nanobot | **17002** | MCP tool-calling, SSE 流式对话, 从源码构建 |
| 胶水 | Gateway | **17003** | 聊天代理, WebSocket 推送, 定时任务, JWT 透传 |
| 胶水 | MCP Server | **17004** | 35 个物联网工具, 知识图谱查询, token-gated 写确认 |
| 胶水 | MQTT Bridge | — | 传感器数据 → AI 分析 → 推送 |
| 基础设施 | PostgreSQL | **17011** | 业务数据 + PostGIS 空间扩展 |
| 基础设施 | Valkey | **17012** | 缓存 / Session / JWT token 存储 |
| 基础设施 | Mosquitto | **17013** | MQTT Broker |
| 基础设施 | TDengine | **17014** | 时序数据 (HTTP REST API) |
| 基础设施 | Neo4j | **17015-17016** | 知识图谱 (Bolt + HTTP) |

## 快速部署

### 前置条件

- Docker 24+ & Docker Compose v2
- Java 17+ & Maven 3.8+（或跳过构建 `--skip-build`）
- 服务器需要访问 LLM API（DeepSeek / OpenAI / Anthropic 等）

### 全栈一键部署（推荐）

```bash
# 交互模式 — 脚本会询问 LLM 提供商、API Key、数据库密码等
bash deploy/deploy.sh

# 部分跳过
bash deploy/deploy.sh --skip-build      # 跳过 Maven 构建（JAR 已存在）
bash deploy/deploy.sh --skip-frontend   # 跳过前端（服务器不构建前端）

# 非交互模式 — 通过环境变量预置所有参数
export LLM_PROVIDER=deepseek
export LLM_API_KEY=sk-xxx
export LLM_MODEL=deepseek-v4-flash
export LLM_BASE_URL=https://api.deepseek.com
export DB_PASSWORD=MySecurePass
bash deploy/deploy.sh --yes

# 停止 & 清理（含数据库 volume）
bash deploy/deploy.sh --clean
docker volume rm dongzao_postgres-data  # 彻底清理数据
```

部署流程（8 阶段）：环境检测 → 交互配置 → 启动基础设施 → Maven 构建后端 → 配置 & 构建 nanobot → 构建胶水层镜像 → 全栈启动 → 健康检查验证。

**支持的 LLM 提供商**：`deepseek`、`openai`、`anthropic`、`moonshot`、`zhipu`、`dashscope`、`siliconflow`，及任意 OpenAI 兼容端点（选"其他"）。

### 仅基础设施

```bash
docker compose up -d
```

### 仅胶水层（需后端 + nanobot 已运行）

```bash
docker compose -f deploy/docker-compose.glue.yml up --build
```

## 本地开发

### Python 胶水层

```bash
cd services/gateway     && pip install -e .
cd services/mcp-server  && pip install -e .
cd services/mqtt-bridge && pip install -e .

# 启动 (dev)
cd services/mcp-server && MOCK_DONGZAO=1 MCP_TRANSPORT=sse MCP_PORT=8804 python server.py
cd services/gateway    && python main.py                           # :8803
cd services/mqtt-bridge && python bridge.py

# 测试
python -m pytest services/mcp-server/tests/ services/gateway/tests/ -q
```

### Java 后端

```bash
mvn clean package -DskipTests -pl backend/ruoyi-admin -am
mvn -pl backend/ruoyi-admin spring-boot:run
```

### 温室数据模拟器

```bash
pip install paho-mqtt
python tools/simulator/greenhouse_simulator.py \
  --broker localhost --port 17013 --greenhouses 5 --interval 10
```

## 环境变量

所有密码和连接信息均通过环境变量注入，部署脚本会交互式收集并写入 `deploy/.env` 和 `deploy/.env.full`。

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LLM_PROVIDER` | — (必填) | deepseek / openai / anthropic / moonshot / zhipu / dashscope / siliconflow / custom |
| `LLM_API_KEY` | — (必填) | API 密钥 |
| `LLM_BASE_URL` | 按提供商 | API 地址（例如 `https://api.deepseek.com`） |
| `LLM_MODEL` | gpt-4o | 模型名称（例如 `deepseek-v4-flash`） |
| `DB_PASSWORD` | password | PostgreSQL 密码（首次初始化后不可改，需删 volume） |
| `VALKEY_PASSWORD` | 自动生成 | Redis 密码 |
| `TDENGINE_PASSWORD` | taosdata | TDengine 密码 |
| `NEO4J_PASSWORD` | <NEO4J_PASSWORD> | Neo4j 密码（至少 8 位） |
| `JWT_SECRET` | 自动生成 | JWT 签名密钥 (HS512, ≥64 字符，须与后端一致) |
| `BACKEND_PORT` | 17001 | 后端端口 |
| `GATEWAY_PORT` | 17003 | Gateway 端口 |
| `MCP_PORT` | 17004 | MCP Server 端口 |
| `NANOBOT_PORT` | 17002 | nanobot API 端口 |
| `UI_PORT` | 17000 | 前端端口 |

> **注意**：PostgreSQL 密码在数据库 volume 首次创建时生效。如需修改密码，必须 `docker volume rm dongzao_postgres-data` 后重新部署。

## MCP 工具列表 (35 tools)

| 领域 | 工具 | 类型 |
|------|------|------|
| 大棚 & 设备 | `list_greenhouses`, `get_greenhouse`, `list_devices`, `get_device_status` | 只读 |
| 实时 & 历史 | `get_realtime_data`, `query_history`, `query_history_aggregated`, `query_abnormal_data`, `query_data_quality` | 只读 |
| 统计 | `get_stats`, `compare_stats`, `correlation_analysis` | 只读 |
| 告警 | `get_alarms`, `get_alarm_detail`, `get_unhandled_alarm_count`, `confirm_alarm`, `resolve_alarm`, `close_alarm`, `mark_false_alarm` | 读+写 |
| 阈值 | `get_thresholds`, `set_threshold` | 读+写 |
| 静默 | `get_silence_config`, `set_silence_config` | 读+写 |
| 物候期 | `get_phenophase` | 只读 |
| GIS | `get_gis_location` | 只读 |
| 订阅 | `get_my_subscriptions`, `subscribe_alarm`, `unsubscribe_alarm` | 读+写 |
| 报表 | `list_reports`, `generate_daily_report`, `generate_greenhouse_report` | 读+写 |
| 知识库 | `query_planting_knowledge` | 只读 |
| 知识图谱 | `search_knowledge_graph`, `get_related_entities`, `list_knowledge_categories` | 只读 |

写操作使用 token-gated 二次确认机制：首次调用返回确认 token，用户同意后携带 token 再次调用才生效。

## 鉴权说明

Gateway 验证 JWT 时**不校验 HMAC-SHA512 签名**——Java JJWT 与 Python PyJWT 的签名实现不兼容。改为从 JWT 中提取 `login_user_key`，在 Valkey 中查找 `login_tokens:{uuid}` 确认 token 有效性。此方式与 Java 后端的 token 验证逻辑等价，且支持即时踢人下线。

## 常见问题

### 后端启动报 `relation "xxx" does not exist`

PostgreSQL initdb 脚本执行中断。通常是旧 volume 残留导致。解决：
```bash
docker compose down
docker volume rm dongzao_postgres-data
bash deploy/deploy.sh
```

### nanobot 反复重启 / `No API key configured`

nanobot 配置文件格式不兼容。检查 `deploy/nanobot-config/config.json`：
- provider 名必须是注册表中的名称（`deepseek`/`openai`/`custom` 等），不能是 `openai_compat`
- 不要包含 `systemPrompt` 等非 schema 字段

### AI 回复"没有找到大棚数据"

MCP 工具未被加载。检查 nanobot 日志：
```bash
docker logs nanobot | grep -i mcp
```
如果出现 `blocked unsafe URL`，说明 SSRF 保护拦截了 Docker 内网地址。在配置 `tools.ssrfWhitelist` 中添加 `["172.16.0.0/12"]`。

### Gateway 返回 401 / token 签名无效

通常是 JWT_SECRET 不一致或浏览器缓存了旧 token。重新登录获取新 token 即可。

## API 示例

### 聊天 (Gateway SSE)

```bash
curl -N -X POST http://localhost:17003/api/chat \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"message": "列出所有大棚", "session_id": "demo"}'
```

### 查看部署状态

```bash
# 容器状态
docker compose -f deploy/docker-compose-full.yml ps

# 服务日志
docker compose -f deploy/docker-compose-full.yml logs -f [服务名]

# 健康检查
curl http://localhost:17001/api/health       # Java 后端
curl http://localhost:17002/v1/models        # nanobot
curl http://localhost:17003/api/health       # Gateway
curl http://localhost:17004/v1/health        # MCP Server

# 测试 AI 对话
TOKEN=$(curl -s -X POST http://localhost:17001/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")
curl -N -X POST http://localhost:17003/api/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"列出所有大棚","session_id":"demo"}'
```

## 许可证

Apache License 2.0
