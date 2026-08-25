# nanobot AI Agent — 详细说明与项目集成文档

> **版本**: v1.0  
> **最后更新**: 2026-07-06  
> **nanobot 版本**: v0.2.1  
> **文档范围**: nanobot 架构原理 + 冬枣项目集成方式

---

## 目录

1. [nanobot 简介](#1-nanobot-简介)
2. [核心架构](#2-核心架构)
3. [Agent Loop 工作原理](#3-agent-loop-工作原理)
4. [MCP 协议集成](#4-mcp-协议集成)
5. [LLM Provider 注册表](#5-llm-provider-注册表)
6. [配置系统](#6-配置系统)
7. [OpenAI 兼容 API](#7-openai-兼容-api)
8. [会话与记忆管理](#8-会话与记忆管理)
9. [工具系统](#9-工具系统)
10. [部署方式](#10-部署方式)
11. [冬枣项目如何复用 nanobot](#11-冬枣项目如何复用-nanobot)
12. [nanobot 配置生成](#12-nanobot-配置生成)
13. [故障排查](#13-故障排查)

---

## 1. nanobot 简介

nanobot 是一个开源、超轻量级的个人 AI Agent 框架，由香港大学数据科学实验室 (HKUDS) 开发维护。

**核心定位**:
- 保持 Agent 核心小而可读
- 提供实际长期运行所需的实用组件：WebUI、聊天渠道、工具、记忆、MCP、模型路由、自动化和部署
- 支持 30+ LLM 提供商、15+ 聊天渠道
- MIT 许可，可自由修改和部署

**关键特性**:

| 特性 | 说明 |
|------|------|
| 持久工作流 | 目标、记忆、工具和聊天上下文在长时间运行中保持 |
| 聊天原生 | WebUI、API、Telegram、Feishu、Slack、Discord、Teams、Email |
| 模型自由 | OpenAI 兼容 API、本地 LLM、图片生成、搜索、回退模型 |
| 小核心 | 可读的内部结构，内置 MCP、记忆、部署和自动化 |
| 自主可控 | 检查、定制、自托管和扩展，无需庞大平台 |

---

## 2. 核心架构

### 2.1 架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                      nanobot 架构                           │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │  Telegram   │  │  Discord    │  │  Feishu     │  ...   │
│  │  Channel    │  │  Channel    │  │  Channel    │        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘        │
│         │                │                │                 │
│         └────────────────┼────────────────┘                 │
│                          │                                  │
│                    ┌─────▼─────┐                            │
│                    │ MessageBus│  (异步消息总线)              │
│                    │  queue.py │                            │
│                    └─────┬─────┘                            │
│                          │                                  │
│                    ┌─────▼─────┐                            │
│                    │ AgentLoop │  (核心处理引擎)              │
│                    │  loop.py  │                            │
│                    └─────┬─────┘                            │
│                          │                                  │
│              ┌───────────┼───────────┐                      │
│              │           │           │                      │
│        ┌─────▼─────┐ ┌──▼──┐ ┌─────▼─────┐                │
│        │AgentRunner│ │Tools│ │  Memory   │                │
│        │ runner.py │ │     │ │ memory.py │                │
│        └─────┬─────┘ └──┬──┘ └───────────┘                │
│              │           │                                  │
│              │     ┌─────▼─────┐                            │
│              │     │ MCP Client│  (连接 MCP Server)          │
│              │     │  mcp.py   │                            │
│              │     └───────────┘                            │
│              │                                              │
│        ┌─────▼─────┐                                        │
│        │  LLM API  │  (OpenAI/Anthropic/...)                │
│        └───────────┘                                        │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 源码结构

```
nanobot-main/
├── nanobot/                    # 核心 Python 包
│   ├── agent/                  # Agent 核心
│   │   ├── loop.py             # AgentLoop — 核心处理引擎
│   │   ├── runner.py           # AgentRunner — LLM 对话循环
│   │   ├── context.py          # 上下文构建器
│   │   ├── memory.py           # 记忆系统 (Dream 两阶段)
│   │   ├── autocompact.py      # 自动上下文压缩
│   │   ├── hook.py             # Agent 钩子系统
│   │   ├── subagent.py         # 子 Agent 管理
│   │   ├── skills.py           # 技能加载器
│   │   ├── model_presets.py    # 模型预设切换
│   │   └── tools/              # 工具系统
│   │       ├── registry.py     # 工具注册表
│   │       ├── mcp.py          # MCP 客户端
│   │       ├── filesystem.py   # 文件系统工具
│   │       ├── shell.py        # Shell 执行工具
│   │       ├── web.py          # Web 搜索/抓取
│   │       ├── search.py       # 搜索工具
│   │       ├── cron.py         # 定时任务工具
│   │       ├── spawn.py        # 子 Agent 生成
│   │       ├── long_task.py    # 长期任务/持续目标
│   │       ├── image_generation.py  # 图片生成
│   │       └── ...             # 更多工具
│   ├── api/                    # OpenAI 兼容 API
│   │   └── server.py           # HTTP API 服务器
│   ├── providers/              # LLM 提供商
│   │   ├── base.py             # 提供商基类
│   │   ├── registry.py         # 提供商注册表 (30+)
│   │   ├── factory.py          # 提供商工厂
│   │   ├── anthropic_provider.py
│   │   ├── openai_compat_provider.py
│   │   └── ...
│   ├── channels/               # 聊天渠道
│   │   ├── telegram/
│   │   ├── discord/
│   │   ├── feishu/
│   │   └── ...                 # 15+ 渠道
│   ├── bus/                    # 消息总线
│   │   ├── queue.py            # 异步消息队列
│   │   └── events.py           # 事件定义
│   ├── session/                # 会话管理
│   │   ├── manager.py          # 会话管理器
│   │   └── goal_state.py       # 持续目标状态
│   ├── config/                 # 配置系统
│   │   ├── schema.py           # Pydantic 配置模型
│   │   └── loader.py           # 配置加载器
│   ├── skills/                 # 内置技能
│   ├── cron/                   # 定时任务服务
│   ├── security/               # 安全模块
│   └── web/                    # WebUI (React SPA)
├── bridge/                     # 聊天桥接 (WhatsApp 等)
├── webui/                      # WebUI 源码 (Vite + React)
├── tests/                      # 测试
├── Dockerfile                  # Docker 构建
├── pyproject.toml              # 项目元数据
└── entrypoint.sh               # Docker 入口脚本
```

### 2.3 核心数据流

```
消息输入 (Channel)
    │
    ▼
InboundMessage → MessageBus.publish()
    │
    ▼
AgentLoop.consume()
    ├── 恢复会话 (Session)
    ├── 构建上下文 (ContextBuilder)
    ├── 检查命令 (/help, /model, etc.)
    ├── 运行 Agent (AgentRunner)
    │       │
    │       ▼
    │   ┌─────────────────────────────┐
    │   │  Agent Runner Loop          │
    │   │                             │
    │   │  1. 发送消息到 LLM           │
    │   │  2. 接收响应 (可能含工具调用) │
    │   │  3. 如果有工具调用:          │
    │   │     a. 执行工具              │
    │   │     b. 将结果附加到消息       │
    │   │     c. 回到步骤 1            │
    │   │  4. 如果无工具调用: 完成      │
    │   │                             │
    │   │  最多 max_tool_iterations 轮│
    │   └─────────────────────────────┘
    │
    ├── 保存会话
    └── 发布 OutboundMessage
            │
            ▼
        Channel → 用户
```

---

## 3. Agent Loop 工作原理

### 3.1 AgentLoop (`loop.py`)

AgentLoop 是 nanobot 的核心处理引擎，管理整个 Agent 的生命周期。

**关键职责**:
- 管理会话键 (session key)
- 协调钩子 (hooks)
- 构建上下文
- 分发命令
- 运行 Agent Runner
- 保存会话

**状态机**:

```
RESTORE → COMPACT → COMMAND → BUILD → RUN → SAVE → RESPOND → DONE
    │         │         │        │       │       │          │
    └─────────┴─────────┴────────┴───────┴───────┴──────────┘
                        (错误时跳转)
```

### 3.2 AgentRunner (`runner.py`)

AgentRunner 处理实际的 LLM 对话循环。

**核心循环**:

```python
while iterations < max_tool_iterations:
    # 1. 发送消息到 LLM
    response = await provider.chat(messages, tools=tool_definitions)
    
    # 2. 检查是否有工具调用
    if response.tool_calls:
        for tool_call in response.tool_calls:
            # 3. 执行工具
            result = await execute_tool(tool_call)
            # 4. 将结果附加到消息
            messages.append(ToolResult(tool_call.id, result))
    else:
        # 5. 无工具调用，完成
        break
    
    iterations += 1
```

**关键参数**:

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `max_tool_iterations` | 200 | 最大工具调用轮数 |
| `max_tool_result_chars` | 16000 | 工具结果最大字符数 |
| `max_concurrent_subagents` | 1 | 最大并发子 Agent 数 |

### 3.3 上下文构建 (`context.py`)

ContextBuilder 负责构建发送给 LLM 的完整上下文。

**上下文组成**:
1. **系统提示** (System Prompt) — Agent 的身份和行为指令
2. **技能** (Skills) — 从 `skills/` 目录加载的 Markdown 技能文件
3. **工具定义** — 所有可用工具的 JSON Schema
4. **会话历史** — 之前的对话记录
5. **当前消息** — 用户输入

### 3.4 记忆系统 (`memory.py`)

nanobot 使用 Dream 两阶段记忆巩固:

```
阶段 1: 即时记忆
    └── 每轮对话直接保存到会话历史

阶段 2: Dream 巩固 (定期)
    ├── 读取历史会话
    ├── 使用 LLM 提取关键信息
    ├── 去重和合并
    └── 保存到长期记忆文件
```

**配置**:
```json
{
  "agents": {
    "defaults": {
      "dream": {
        "enabled": true,
        "interval_h": 2
      }
    }
  }
}
```

---

## 4. MCP 协议集成

### 4.1 MCP 是什么

MCP (Model Context Protocol) 是一个标准化协议，允许 AI Agent 连接外部工具服务器。nanobot 作为 MCP 客户端，可以连接任何实现 MCP 协议的服务器。

### 4.2 nanobot 的 MCP 实现

**客户端实现**: `nanobot/agent/tools/mcp.py`

**支持的传输模式**:

| 模式 | 说明 | 配置 |
|------|------|------|
| `stdio` | 标准输入输出 | `command` + `args` |
| `sse` | Server-Sent Events | `url` |
| `streamableHttp` | HTTP 流式 | `url` |
| `auto` | 自动检测 | 根据配置自动选择 |

**连接流程**:

```
nanobot 启动
    │
    ▼
读取 config.json → tools.mcpServers
    │
    ▼
对每个 MCP Server:
    ├── 验证 URL 安全性 (SSRF 防护)
    ├── 建立连接 (stdio/sse/http)
    ├── 获取工具列表 (tools/list)
    ├── 包装为 nanobot Tool
    └── 注册到 ToolRegistry
    │
    ▼
Agent Loop 可调用 MCP 工具
```

### 4.3 MCP 工具包装

每个 MCP 工具被包装为 `MCPToolWrapper`:

```python
class MCPToolWrapper(Tool):
    """包装单个 MCP 工具为 nanobot Tool"""
    
    async def execute(self, **kwargs) -> str:
        # 1. 调用 MCP Server 的 tools/call
        result = await self._session.call_tool(self._mcp_name, kwargs)
        
        # 2. 处理结果
        return self._format_result(result)
```

### 4.4 SSRF 防护

nanobot 内置 SSRF (Server-Side Request Forgery) 防护:

```json
{
  "tools": {
    "ssrfWhitelist": ["172.16.0.0/12", "10.0.0.0/8", "192.168.0.0/16"]
  }
}
```

- 默认阻止所有非公网 URL
- 白名单中的 CIDR 范围被允许
- 每个 HTTP 请求都经过验证
- 重定向目标也经过验证

### 4.5 断线重连

nanobot 支持 MCP Server 断线自动重连:

```
工具调用失败
    │
    ▼
检查是否为瞬态错误 (ClosedResourceError, BrokenResourceError, ...)
    │
    ├── 是 → 重新连接 MCP Server → 重试工具调用
    └── 否 → 返回错误给 LLM
```

---

## 5. LLM Provider 注册表

### 5.1 支持的提供商

nanobot 支持 30+ LLM 提供商:

| 提供商 | 后端类型 | 默认 API 地址 |
|--------|---------|--------------|
| `openai` | openai_compat | https://api.openai.com/v1 |
| `anthropic` | anthropic | https://api.anthropic.com |
| `deepseek` | openai_compat | https://api.deepseek.com |
| `openrouter` | openai_compat | https://openrouter.ai/api/v1 |
| `moonshot` | openai_compat | https://api.moonshot.cn/v1 |
| `zhipu` | openai_compat | https://open.bigmodel.cn/api/paas/v4 |
| `dashscope` | openai_compat | — |
| `siliconflow` | openai_compat | — |
| `groq` | openai_compat | https://api.groq.com/openai/v1 |
| `ollama` | openai_compat | http://localhost:11434/v1 |
| `vllm` | openai_compat | http://localhost:8000/v1 |
| `lm_studio` | openai_compat | http://localhost:1234/v1 |
| `azure_openai` | azure_openai | — |
| `bedrock` | bedrock | — |
| `github_copilot` | github_copilot | — |
| `custom` | openai_compat | 需手动配置 |

### 5.2 Provider 注册表 (`providers/registry.py`)

每个提供商通过 `ProviderSpec` 定义:

```python
@dataclass(frozen=True)
class ProviderSpec:
    name: str              # 配置字段名
    keywords: tuple        # 模型名匹配关键词
    env_key: str           # API Key 环境变量
    backend: str           # 后端实现类型
    default_api_base: str  # 默认 API 地址
    is_gateway: bool       # 是否为网关 (OpenRouter 等)
    is_local: bool         # 是否为本地部署
    ...
```

**模型匹配流程**:

```
用户请求模型: "deepseek-v4-flash"
    │
    ▼
遍历 PROVIDERS 注册表
    ├── 检查 keywords 匹配
    ├── 检查 api_key 前缀
    ├── 检查 api_base 关键词
    └── 返回匹配的 ProviderSpec
    │
    ▼
使用匹配的 Provider 发送请求
```

### 5.3 回退模型

nanobot 支持自动回退到备用模型:

```json
{
  "agents": {
    "defaults": {
      "provider": "deepseek",
      "model": "deepseek-v4-flash",
      "fallbackModels": [
        {"model": "gpt-4o", "provider": "openai"},
        {"model": "claude-sonnet-4-6", "provider": "anthropic"}
      ]
    }
  }
}
```

当主模型不可用时，自动尝试回退模型。

---

## 6. 配置系统

### 6.1 配置文件位置

默认路径: `~/.nanobot/config.json`

### 6.2 配置结构

```json
{
  "providers": {
    "<provider_name>": {
      "apiKey": "sk-xxx",
      "apiBase": "https://..."
    }
  },
  "agents": {
    "defaults": {
      "provider": "deepseek",
      "model": "deepseek-v4-flash",
      "maxToolIterations": 15,
      "timezone": "Asia/Shanghai",
      "botName": "冬枣AI助手",
      "botIcon": "🌱"
    }
  },
  "api": {
    "host": "0.0.0.0",
    "port": 8900
  },
  "tools": {
    "ssrfWhitelist": ["172.16.0.0/12"],
    "mcpServers": {
      "<server_name>": {
        "transport": "sse",
        "url": "http://mcp-server:9001/sse",
        "toolTimeout": 30
      }
    }
  },
  "channels": {
    "websocket": { "enabled": true }
  }
}
```

### 6.3 关键配置项

#### Agent 配置 (`agents.defaults`)

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `provider` | string | `"auto"` | LLM 提供商 |
| `model` | string | `"anthropic/claude-opus-4-5"` | 模型名称 |
| `maxToolIterations` | int | `200` | 最大工具调用轮数 |
| `maxTokens` | int | `8192` | 最大生成 token 数 |
| `contextWindowTokens` | int | `65536` | 上下文窗口大小 |
| `temperature` | float | `0.1` | 温度参数 |
| `timezone` | string | `"UTC"` | 时区 |
| `botName` | string | `"nanobot"` | 显示名称 |
| `botIcon` | string | `"🐈"` | 显示图标 |
| `fallbackModels` | list | `[]` | 回退模型列表 |

#### MCP Server 配置 (`tools.mcpServers`)

| 字段 | 类型 | 说明 |
|------|------|------|
| `type` | string | 传输模式: stdio/sse/streamableHttp/auto |
| `command` | string | stdio 模式的命令 |
| `args` | list | stdio 模式的参数 |
| `url` | string | HTTP/SSE 模式的 URL |
| `headers` | dict | 自定义请求头 |
| `toolTimeout` | int | 工具调用超时 (秒) |
| `enabledTools` | list | 启用的工具列表, `["*"]` = 全部 |

#### API 服务器配置 (`api`)

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `host` | string | `"127.0.0.1"` | 监听地址 |
| `port` | int | `8900` | 监听端口 |
| `timeout` | float | `120.0` | 请求超时 (秒) |

---

## 7. OpenAI 兼容 API

### 7.1 端点

nanobot 提供 OpenAI 兼容的 HTTP API:

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/v1/chat/completions` | 聊天补全 (流式/非流式) |
| `GET` | `/v1/models` | 列出可用模型 |

### 7.2 聊天补全请求

**请求体** (OpenAI 格式):
```json
{
  "model": "deepseek-v4-flash",
  "messages": [
    {"role": "user", "content": "列出所有大棚"}
  ],
  "stream": true,
  "session_id": "user-123"
}
```

**流式响应** (SSE):
```
data: {"id":"chatcmpl-xxx","object":"chat.completion.chunk","choices":[{"delta":{"content":"根据"},"index":0}]}

data: {"id":"chatcmpl-xxx","object":"chat.completion.chunk","choices":[{"delta":{"content":"查询"},"index":0}]}

data: {"id":"chatcmpl-xxx","object":"chat.completion.chunk","choices":[{"delta":{},"finish_reason":"stop"}]}

data: [DONE]
```

**非流式响应**:
```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "choices": [
    {
      "index": 0,
      "message": {"role": "assistant", "content": "根据查询结果..."},
      "finish_reason": "stop"
    }
  ]
}
```

### 7.3 会话管理

通过 `session_id` 参数实现多轮对话:

```json
{
  "messages": [{"role": "user", "content": "你好"}],
  "session_id": "user-123"
}
```

同一 `session_id` 的请求共享会话历史，支持多轮上下文。

### 7.4 文件上传

支持通过 `messages` 传递文件:

```json
{
  "messages": [
    {
      "role": "user",
      "content": [
        {"type": "text", "text": "分析这个文件"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
      ]
    }
  ]
}
```

---

## 8. 会话与记忆管理

### 8.1 会话存储

会话数据存储在 `~/.nanobot/workspace/sessions/` 目录:

```
~/.nanobot/workspace/sessions/
├── api:default.json          # API 默认会话
├── user:1001.json            # 用户 1001 的会话
└── alert:GH001:2026-07-06.json  # 告警分析会话
```

### 8.2 会话压缩

nanobot 自动压缩过长的会话历史:

- **触发条件**: 会话消息数超过 `maxMessages` 或 token 预算
- **压缩方式**: 使用 LLM 总结旧消息，保留关键信息
- **配置**:

```json
{
  "agents": {
    "defaults": {
      "sessionTtlMinutes": 30,
      "maxMessages": 120,
      "consolidationRatio": 0.5
    }
  }
}
```

### 8.3 Dream 记忆巩固

Dream 是 nanobot 的长期记忆系统:

```
定期触发 (每 2 小时)
    │
    ▼
读取历史会话
    │
    ▼
LLM 提取关键信息
    │
    ├── 用户偏好
    ├── 重要决策
    ├── 项目上下文
    └── 学到的知识
    │
    ▼
去重和合并
    │
    ▼
保存到 ~/.nanobot/workspace/memory/
```

### 8.4 持续目标 (Sustained Goals)

nanobot 支持跨会话的持续目标:

```json
{
  "session_id": "user-1001",
  "goal": "监控冬枣大棚温度，异常时自动告警"
}
```

目标状态跨会话保持，Agent 会在每轮对话中检查并推进目标。

---

## 9. 工具系统

### 9.1 内置工具

nanobot 提供丰富的内置工具:

| 工具类别 | 工具 | 说明 |
|---------|------|------|
| 文件系统 | `read_file`, `write_file`, `edit_file`, `list_files` | 文件读写 |
| Shell | `execute_shell` | 命令执行 (沙箱) |
| Web | `web_search`, `web_fetch` | 搜索和抓取 |
| MCP | `mcp_<server>_<tool>` | MCP Server 工具 |
| 定时 | `cron` | 定时任务 |
| 子Agent | `spawn_agent` | 生成子 Agent |
| 长期任务 | `long_task` | 持续目标管理 |
| 图片 | `generate_image` | 图片生成 |
| 自身 | `self` | Agent 自我修改 |

### 9.2 工具发现

工具通过两种方式发现:

1. **自动扫描**: `pkgutil` 扫描 `nanobot/agent/tools/` 目录
2. **插件注册**: 通过 `entry_points` 注册第三方工具

### 9.3 MCP 工具命名

MCP 工具被包装为 `mcp_<server>_<tool>` 格式:

```
MCP Server: dongzao
MCP Tool: list_greenhouses
    ↓
nanobot Tool: mcp_dongzao_list_greenhouses
```

### 9.4 工具执行流程

```
LLM 请求工具调用
    │
    ▼
ToolRegistry 查找工具
    │
    ▼
检查工具类型
    ├── 内置工具 → 直接执行
    └── MCP 工具 → 调用 MCP Server
            │
            ▼
        MCP Client 发送 tools/call
            │
            ▼
        MCP Server 执行并返回结果
            │
            ▼
        格式化结果返回给 LLM
```

---

## 10. 部署方式

### 10.1 Docker 部署 (冬枣项目使用)

**Dockerfile**:
```dockerfile
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# 安装 Node.js (WhatsApp bridge 需要)
RUN apt-get update && apt-get install -y nodejs ...

WORKDIR /app

# 安装 Python 依赖
COPY pyproject.toml .
RUN uv pip install --system --no-cache .

# 复制源码
COPY nanobot/ nanobot/
COPY bridge/ bridge/
COPY webui/ webui/

# 构建 WebUI
RUN NANOBOT_FORCE_WEBUI_BUILD=1 uv pip install --system --no-cache .

# 创建用户
RUN useradd -m -u 1000 nanobot

USER nanobot
EXPOSE 18790 8765

ENTRYPOINT ["entrypoint.sh"]
CMD ["status"]
```

**启动命令**:
```bash
# API 模式 (冬枣项目使用)
nanobot serve --verbose

# Gateway 模式 (含 WebUI)
nanobot gateway
```

### 10.2 Docker Compose

```yaml
nanobot:
  build:
    context: ../nanobot-main
    dockerfile: Dockerfile
  image: dongzao-nanobot:latest
  container_name: nanobot
  command: ["serve", "--verbose"]
  ports:
    - "17002:8900"
  volumes:
    - ./nanobot-config/config.json:/home/nanobot/.nanobot/config.json
    - nanobot-workspace:/home/nanobot/workspace
  networks:
    - dongzao
```

### 10.3 健康检查

```bash
# 模型列表
curl http://localhost:8900/v1/models

# 聊天测试
curl -X POST http://localhost:8900/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"hello"}]}'
```

---

## 11. 冬枣项目如何复用 nanobot

### 11.1 复用策略

冬枣项目采用 **零修改复用** 策略 — 直接使用 nanobot 上游代码，不做任何修改。

```
┌─────────────────────────────────────────────────────┐
│              冬枣项目 nanobot 复用方式                │
│                                                     │
│  策略: 源码构建 + 配置注入                           │
│                                                     │
│  ┌──────────────────┐    ┌──────────────────┐       │
│  │ nanobot-main/    │    │ deploy/          │       │
│  │ (上游源码)       │    │ nanobot-config/  │       │
│  │                  │    │ config.json      │       │
│  │ Dockerfile       │ ←──│ (自动生成)       │       │
│  │ nanobot/         │    └──────────────────┘       │
│  └────────┬─────────┘                               │
│           │ docker build                            │
│           ▼                                         │
│  ┌──────────────────┐                               │
│  │ dongzao-nanobot  │                               │
│  │ :latest          │                               │
│  └────────┬─────────┘                               │
│           │ docker run                              │
│           ▼                                         │
│  ┌──────────────────┐                               │
│  │ nanobot 容器      │                               │
│  │                  │                               │
│  │ config.json ← 挂载                               │
│  │ workspace  ← volume                              │
│  └──────────────────┘                               │
└─────────────────────────────────────────────────────┘
```

### 11.2 复用的功能模块

| 功能 | nanobot 模块 | 冬枣项目用途 |
|------|-------------|-------------|
| **AI 推理** | AgentLoop + AgentRunner | 多轮对话、工具调用循环 |
| **MCP 客户端** | `agent/tools/mcp.py` | 连接 MCP Server 获取 IoT 数据 |
| **流式输出** | API Server SSE | Gateway 代理 SSE 流到前端 |
| **会话管理** | Session Manager | 按 session_id 隔离用户对话 |
| **Provider** | Provider Registry | 支持 DeepSeek/OpenAI/Anthropic 等 |
| **SSRF 防护** | Security Network | 阻止访问 Docker 内网地址 |
| **工具注册** | Tool Registry | 自动注册 MCP 工具为 Agent 工具 |

### 11.3 不复用的功能

| 功能 | 原因 |
|------|------|
| 聊天渠道 (Telegram/Discord等) | 冬枣项目使用自有 Gateway + WebSocket |
| WebUI | 冬枣项目使用自有前端 (Vue) |
| 文件系统工具 | IoT 场景不需要 |
| Shell 执行 | 安全考虑，不开放 |
| Dream 记忆 | IoT 场景不需要长期记忆 |
| 图片生成 | 不需要 |

### 11.4 Gateway 与 nanobot 的交互

```
Gateway (FastAPI)                    nanobot (API Server)
    │                                      │
    │ POST /v1/chat/completions            │
    │ {messages, stream: true}             │
    │ ────────────────────────────────────→│
    │                                      │ Agent Loop
    │                                      │   ├── 构建上下文
    │                                      │   ├── 调用 LLM
    │                                      │   ├── 执行 MCP 工具
    │                                      │   └── 生成响应
    │                                      │
    │ ←── SSE Stream ─────────────────────│
    │                                      │
    │ 转发 SSE 到前端                       │
```

**关键点**:
- Gateway 透传用户 JWT 到 Redis (`mcp_jwt:{session_id}`)
- MCP Server 从 Redis 读取 JWT 调用 Java 后端
- nanobot 不感知用户身份，只处理消息和工具调用
- 流式输出通过 SSE 实时传递

### 11.5 MCP 工具调用链

```
用户: "查看1号大棚温度"
    │
    ▼
Gateway → nanobot
    │
    ▼
nanobot Agent Loop
    ├── LLM 决定调用 mcp_dongzao_get_realtime_data
    │
    ▼
MCP Client → MCP Server (:17004)
    │
    ▼
MCP Server
    ├── 参数校验 (validators.py)
    ├── 从 Redis 读取用户 JWT
    ├── 调用 Java 后端 API
    └── 返回 Markdown 结果
    │
    ▼
nanobot ← MCP 结果
    │
    ▼
LLM 生成最终回复
    │
    ▼
Gateway → 前端
```

---

## 12. nanobot 配置生成

### 12.1 自动配置生成

冬枣项目通过 `deploy.sh` 自动生成 nanobot 配置:

```bash
# deploy.sh 中的配置生成逻辑
cat > deploy/nanobot-config/config.json <<EOF
{
  "providers": {
    "${NB_PROVIDER}": {
      "apiKey": "${LLM_API_KEY}",
      "apiBase": "${NB_API_BASE}"
    }
  },
  "agents": {
    "defaults": {
      "provider": "${NB_PROVIDER}",
      "model": "${LLM_MODEL}",
      "maxToolIterations": 15,
      "timezone": "Asia/Shanghai",
      "botName": "冬枣AI助手",
      "botIcon": "🌱"
    }
  },
  "api": {
    "host": "0.0.0.0",
    "port": 8900
  },
  "tools": {
    "ssrfWhitelist": ["172.16.0.0/12", "10.0.0.0/8", "192.168.0.0/16"],
    "mcpServers": {
      "dongzao": {
        "transport": "sse",
        "url": "http://mcp-server:9001/sse",
        "toolTimeout": 30
      }
    }
  }
}
EOF
```

### 12.2 Provider 映射

| 用户选择 | nanobot Provider | 说明 |
|---------|-----------------|------|
| `deepseek` | `deepseek` | DeepSeek 官方 |
| `openai` | `openai` | OpenAI 官方 |
| `anthropic` | `anthropic` | Anthropic 官方 |
| `moonshot` | `moonshot` | Moonshot/Kimi |
| `zhipu` | `zhipu` | 智谱 AI |
| `dashscope` | `dashscope` | 通义千问 |
| `siliconflow` | `siliconflow` | SiliconFlow |
| 其他 | `custom` | 任意 OpenAI 兼容端点 |

### 12.3 配置验证

nanobot 启动时验证配置:

```python
# nanobot/config/schema.py
class Config(BaseSettings):
    agents: AgentsConfig
    providers: ProvidersConfig
    tools: ToolsConfig
    api: ApiConfig
    ...
```

配置错误会导致启动失败，并输出清晰的错误信息。

---

## 13. 故障排查

### 13.1 nanobot 启动失败

**症状**: 容器反复重启

**排查**:
```bash
# 查看日志
docker logs nanobot | tail -50

# 常见错误
# 1. "No API key configured" → 检查 providers 配置
# 2. "Invalid config" → 检查 config.json 格式
# 3. "MCP connection failed" → 检查 MCP Server 地址
```

### 13.2 MCP 工具未加载

**症状**: AI 回复"没有找到数据"

**排查**:
```bash
# 检查 MCP 连接
docker logs nanobot | grep -i mcp

# 常见原因
# 1. "blocked unsafe URL" → SSRF 防护拦截
# 2. "connection refused" → MCP Server 未启动
# 3. "tool not found" → 工具名称不匹配
```

**解决**:
```json
{
  "tools": {
    "ssrfWhitelist": ["172.16.0.0/12", "10.0.0.0/8", "192.168.0.0/16"]
  }
}
```

### 13.3 流式输出中断

**症状**: SSE 流突然停止

**排查**:
```bash
# 检查超时配置
# nanobot 默认 API timeout: 120s
# Gateway httpx timeout: 300s

# 检查 nanobot 日志
docker logs nanobot | grep -i timeout
```

### 13.4 会话不保持

**症状**: 每次对话都是新会话

**排查**:
```bash
# 检查 session_id 是否传递
# Gateway chat.py 中:
# session_id = body.get("session_id") or uuid.uuid4().hex

# 检查会话文件
docker exec nanobot ls -la /home/nanobot/.nanobot/workspace/sessions/
```

### 13.5 工具调用超时

**症状**: MCP 工具调用超时

**配置**:
```json
{
  "tools": {
    "mcpServers": {
      "dongzao": {
        "toolTimeout": 30
      }
    }
  }
}
```

**优化**:
- 增加 `toolTimeout` 值
- 优化 MCP Server 响应速度
- 减少不必要的工具调用轮数 (`maxToolIterations`)

---

**文档版本**: v1.0  
**最后更新**: 2026-07-06  
**维护者**: 冬枣智慧大棚项目组
