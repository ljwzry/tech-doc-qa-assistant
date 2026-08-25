# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

双项目仓库："冬枣种植智慧大棚物联网平台"(Java/Vue) + "nanobot AI Agent 胶水层"(Python)。当前工作集中在胶水层。

## Key Commands

### Python 胶水层 (services/)

```bash
# Install (每个服务独立 venv 或全局 pip install -e .)
cd services/gateway && pip install -e .
cd services/mcp-server && pip install -e .
cd services/mqtt-bridge && pip install -e .

# Run all tests
python -m pytest services/mcp-server/tests/ services/gateway/tests/ -q

# Run a single test file
python -m pytest services/mcp-server/tests/test_mcp_server.py -v

# Mock integration test (no backend/nanobot needed)
cd services/mcp-server && python tests/test_integration_mock.py

# Start services (dev mode, before full Docker Compose)
cd services/mcp-server && MOCK_DONGZAO=1 MCP_TRANSPORT=sse MCP_PORT=17004 python server.py
cd services/gateway && python main.py                              # :17003
cd services/mqtt-bridge && python bridge.py                         # no port
cd nanobot-main && nanobot run                                     # :17002
```

### Java 冬枣后端 (backend/)

```bash
# Build (from project root — pom.xml resolves backend/ modules)
mvn clean package -DskipTests

# Run Spring Boot (from project root)
mvn -pl backend/ruoyi-admin spring-boot:run
```

### Infrastructure

```bash
# 共享 infra（postgres + tdengine + valkey + mosquitto + neo4j）
docker compose up -d
docker compose ps
docker compose down

# 全栈一键部署（交互式，infra + backend + nanobot + glue + frontend）
bash deploy/deploy.sh              # 交互模式，逐步确认
bash deploy/deploy.sh --yes        # 非交互模式
bash deploy/deploy.sh --clean      # 停止并清理所有容器
bash deploy/deploy.sh --skip-build # 跳过 Maven 构建

# 仅胶水层 — 本地开发
docker compose -f deploy/docker-compose.glue.yml up --build   # 一键启动 gateway + mcp + mqtt
cd services/gateway     && docker compose up --build            # 单独启动 gateway
cd services/mcp-server  && MOCK_DONGZAO=1 docker compose up --build  # 单独启动 mcp-server (mock)
cd services/mqtt-bridge && docker compose up --build            # 单独启动 mqtt-bridge

# 仅应用层（需先启动基础设施 docker compose up -d）
docker compose -f deploy/docker-compose-full.yml up --build
```

## Architecture: Glue Layer (this branch)

```
frontend/mp ──→ Gateway(:17003) ──→ nanobot(:17002) ──→ LLM (OpenAI/Claude)
                    │                      │
                    │              ┌───────┘ MCP protocol
                    │              ▼
                    │         MCP Server(:17004) ──→ dongzao backend(:17001)
                    │
               MQTT Bridge ──→ mosquitto(:17013) ← sensors
                    │
                    └──→ Gateway internal push → WS → user
```

**Four independent Python services, zero modifications to either upstream project:**

| Service | Dir | Port | Role |
|---------|-----|------|------|
| **Gateway** | `services/gateway/` | 17003 | JWT auth (reuses dongzao JWT+Redis), SSE chat proxy, WebSocket push, cron task scheduler |
| **nanobot** | `nanobot-main/` | 17002 | AI Agent — MCP tool-calling loop，多轮对话，流式 SSE 输出 |
| **MCP Server** | `services/mcp-server/` | 17004 | 33 MCP tools wrapping dongzao REST APIs + 知识图谱查询, 6-layer param validation, token-gated write confirmations |
| **MQTT Bridge** | `services/mqtt-bridge/` | none | Subscribes `dongzao/greenhouse/#`, detects critical/warning, injects into nanobot for AI analysis, pushes results via Gateway |

### nanobot key design decisions

- 使用上游 nanobot 项目，不做自写 Agent。Gateway 通过 `NANOBOT_API_URL` 指向 nanobot
- nanobot 通过 MCP 协议调用 MCP Server 获取 IoT 数据，自动执行 tool-calling loop
- Gateway `chat.py`: `stream_chat()` 代理 SSE 流；`inject_message()` 供 Scheduler / MQTT Bridge 非流式注入

### MCP Server key design decisions

- **33 tools** across IoT APIs (29) + knowledge graph (4): `search_knowledge_graph`, `get_related_entities`, `list_knowledge_categories`, `walk_relations`
- Knowledge graph uses **dual backend**: default file-based (reads `tools/crawler/output/*.json`), auto-switches to Neo4j when `NEO4J_URI` is set
- Write operations use **token-gated two-phase confirmation**: first call returns a random `confirmation_token`, second call must carry the same token within 5 minutes. Token is single-use, stored in memory. LLM cannot bypass this.
- `MockDongzaoClient` in `mock_backend.py` replaces `DongzaoClient` when `MOCK_DONGZAO=1` — full integration test surface without real backend.
- Validators (`validators.py`) treat all LLM parameters as untrusted: type check → injection detection → ID format → physical range → entity existence → token gate. `HardBlockError` for unrecoverable, `ValidationError` for recoverable (LLM can retry).
- All tool outputs are plain Markdown strings (not raw JSON) — designed for LLM consumption.

### Knowledge Graph & Crawler

```
tools/crawler/              # 知识爬虫 — 从农业网站抓取冬枣种植知识
  main.py                   # 编排：爬取 → LLM抽取 → 去重 → 输出 JSON
  spiders/                  # 4站点爬虫 (ymt/ahnw/baike/nkb)
  extractor/                # LLM 实体关系提取
  models/                   # Entity/Relation 数据模型
  scripts/
    import_to_neo4j.py      # JSON → Neo4j 导入
  output/                   # entities.json + relations.json
```

- `knowledge_graph.py` — 双后端：文件模式 (默认) / Neo4j (设置 `NEO4J_URI`)
- 导入: `python tools/crawler/scripts/import_to_neo4j.py` (需 Neo4j 运行)

### Gateway key design decisions

- `auth.py`: `_try_get_user()` requires `Authorization: Bearer <dongzao_JWT>` header. Validates HS512 JWT, looks up `login_tokens:{uuid}` in Redis. **No dev backdoor** (`?user_id=` bypass was removed).
- `chat.py`: `stream_chat()` proxies SSE from nanobot; `inject_message()` is non-streaming for scheduler/bridge use.
- `ws_manager.py`: per-user connection pool, 30s heartbeat, survives broken connections.
- `scheduler.py`: APScheduler with cron/interval/at triggers, persisted to JSON, injects nanobot on fire.

### Test structure

- `services/mcp-server/tests/test_mcp_server.py` — 42 unit tests for validators + tools + client
- `services/mcp-server/tests/test_brutal_validators.py` — 54 edge-case tests (injection, boundaries, concurrency)
- `services/mcp-server/tests/test_brutal_tools.py` — 19 integration-style tests (error recovery, SQL injection, flows)
- `services/mcp-server/tests/test_integration_mock.py` — 10-scenario agent conversation simulation (69 checks)
- `services/gateway/tests/test_brutal_gateway.py` — 26 tests (auth, scheduler, WS manager, config)

### Environment variables for glue services

```
DONGZAO_API_URL=http://localhost:17001     # mcp-server + gateway
NANOBOT_API_URL=http://localhost:17002     # gateway + mqtt-bridge
REDIS_HOST=localhost REDIS_PORT=17012      # gateway JWT validation
JWT_SECRET=abcdefghijklmnopqrstuvwxyz     # gateway (match dongzao app.yml)
MOCK_DONGZAO=1                            # mcp-server (use in-memory data)
MCP_TRANSPORT=sse MCP_PORT=17004           # mcp-server (HTTP mode)
MQTT_BROKER=localhost MQTT_PORT=17013      # mqtt-bridge
GATEWAY_URL=http://localhost:17003         # mqtt-bridge
NEO4J_URI=bolt://localhost:17015           # mcp-server (知识图谱，可选)
KG_DATA_DIR=./tools/crawler/output         # mcp-server (文件模式知识图谱路径)
```

### nanobot integration

Gateway 直接指向 nanobot 服务：

```bash
# Gateway
NANOBOT_API_URL=http://localhost:17002

# nanobot 配置：tools.mcp_servers 指定 MCP Server 地址
# 在 nanobot 启动配置中设置：
{"tools": {"mcp_servers": {"dongzao": {"transport": "sse", "url": "http://localhost:17004/sse"}}}}
```

## Architecture: Java Backend (ruoyi-iot)

Standard RuoYi-Vue v3.9.2 multi-module Maven project, Spring Boot 4.x + MyBatis + PostgreSQL + TDengine.

- **ruoyi-admin** — entry + controllers
- **ruoyi-framework** — security (JWT HS512 filter chain), config
- **ruoyi-system** — user/role/menu management
- **ruoyi-iot** — greenhouse, device, alarm, threshold, phenophase, stats, GIS, realtime, history controllers
- **ruoyi-ui** — Vue 2.x frontend

Auth: stateless JWT + stateful Redis. Token contains `login_user_key` (UUID) + `sub` (username). Redis key = `login_tokens:{uuid}` with 30min TTL. No `exp` claim in JWT itself.

Total: 12 IoT controllers with ~83 endpoints. IoT domain entities: Greenhouse, Device, AlarmRecord, Threshold, Phenophase, Batch, AggregatedData, SilenceConfig, UserAlarmSubscription, AuditLog.
