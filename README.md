# TechDoc QA Assistant — 技术文档智能问答助手

基于 RAG（检索增强生成）架构的智能问答系统，支持多项目文档隔离、混合检索（向量 + 关键词）和互联网搜索兜底，为团队提供精准的技术文档问答服务。

## 架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                         用户浏览器                                │
│                   Streamlit 前端 (localhost:8501)                 │
│   ┌───────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│   │  对话问答区域   │  │ 文档管理面板  │  │  项目选择器 / 上传  │  │
│   └───────┬───────┘  └──────┬───────┘  └─────────┬──────────┘  │
└───────────┼─────────────────┼────────────────────┼──────────────┘
            │ SSE 流式响应      │ REST API           │ REST API
            ▼                  ▼                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI 后端 (localhost:8000)                  │
│                                                                   │
│  ┌─────────────┐  ┌──────────────────┐  ┌────────────────────┐  │
│  │  Chat 路由   │  │  Documents 路由   │  │  Sessions 路由     │  │
│  │  /api/chat   │  │  /api/documents  │  │  /api/sessions    │  │
│  │  /api/stream │  │  /api/upload     │  │                   │  │
│  └──────┬──────┘  └────────┬─────────┘  └───────────────────┘  │
│         │                   │                                     │
│         ▼                   ▼                                     │
│  ┌──────────────────────────────────┐  ┌────────────────────┐   │
│  │     LangGraph ReAct Agent        │  │  文档处理管道        │   │
│  │                                  │  │  Loader → Splitter  │   │
│  │  ┌────────┐    ┌──────────────┐  │  │  → Embeddings       │   │
│  │  │ Agent  │───▶│ Tool Node    │  │  │  → Chroma + BM25    │   │
│  │  │ Node   │◀───│ (rag_search  │  │  └────────────────────┘   │
│  │  └────────┘    │  web_search) │  │                            │
│  │       │        └──────┬───────┘  │                            │
│  │       │   ┌───────────┘          │                            │
│  │       ▼   ▼                       │                            │
│  │  ┌──────────────────────────┐     │                            │
│  │  │    混合检索引擎            │     │                            │
│  │  │                          │     │                            │
│  │  │  ┌─────────┐ ┌────────┐  │     │                            │
│  │  │  │ ChromaDB │ │  BM25  │  │     │                            │
│  │  │  │ 向量检索  │ │ 关键词  │  │     │                            │
│  │  │  └────┬─────┘ └───┬────┘  │     │                            │
│  │  │       │  RRF 融合  │       │     │                            │
│  │  │       └─────┬─────┘       │     │                            │
│  │  └─────────────┼─────────────┘     │                            │
│  │                │                   │                            │
│  │    ┌───────────┘                   │                            │
│  │    ▼                               │                            │
│  │  ┌──────────┐                      │                            │
│  │  │ LLM 推理  │                      │                            │
│  │  │ DeepSeek  │                      │                            │
│  │  │ /Ollama   │                      │                            │
│  │  └──────────┘                      │                            │
│  └────────────────────────────────────┘                            │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                        数据层                                │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐  │   │
│  │  │ data/docs │  │ chroma_db│  │bm25_index│  │ sessions/ │  │   │
│  │  │ (文档原文) │  │ (向量库)  │  │(倒排索引) │  │ (会话记录) │  │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └───────────┘  │   │
│  └─────────────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────────┘
```

## 核心工作流

```
用户提问
  │
  ▼
┌───────────────────┐
│  项目范围自动识别   │  优先级: 查询含项目名 > 自身指代 > 使用说明 > 全库
└────────┬──────────┘
         │
         ▼
┌───────────────────┐     未命中      ┌─────────────────┐
│  rag_search 工具   │──────────────▶ │  web_search 工具  │
│  (知识库检索)      │                │  (互联网搜索兜底)  │
└────────┬──────────┘                └────────┬────────┘
         │ 命中                                │
         ▼                                     ▼
┌───────────────────────────────────────────────────────┐
│              LLM 基于检索结果生成回答                    │
│              SSE 流式输出 → 前端实时渲染                 │
│              保存对话记录到 session 文件                │
└───────────────────────────────────────────────────────┘
```

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| **Agent 框架** | LangGraph 0.2 | ReAct 模式，支持工具调用循环（最多 3 轮） |
| **LLM** | DeepSeek-V3 / Ollama | 通过 SiliconFlow 中转或本地部署 |
| **向量数据库** | ChromaDB 0.5 | 本地持久化，支持元数据过滤 |
| **关键词检索** | rank-bm25 + jieba | 中文分词，大小写不敏感 |
| **Embedding** | BGE-small-zh | 100MB 轻量模型，CPU 友好 |
| **后端** | FastAPI + Uvicorn | 异步 API，SSE 流式响应 |
| **前端** | Streamlit | 文档管理 + 对话界面 |
| **部署** | Docker + Docker Compose | 双容器，模型缓存挂载 |
| **评估** | RAGAS | 忠实度、相关性、上下文精确率/召回率 |

## 项目结构

```
tech-doc-qa-assistant/
├── app/
│   ├── main.py                 # FastAPI 应用入口，lifespan 预加载
│   ├── config.py               # 环境变量配置管理
│   ├── api/
│   │   ├── chat.py             # 聊天 API（同步 + SSE 流式）
│   │   └── documents.py        # 文档上传/删除/列表/重建索引
│   ├── agent/
│   │   ├── graph.py            # LangGraph 工作流定义
│   │   ├── nodes.py            # Agent 节点（LLM 绑定 + 重试）
│   │   ├── tools.py            # rag_search / web_search 工具
│   │   ├── prompts.py          # 系统提示词（项目识别规则）
│   │   └── state.py            # Agent 状态定义
│   ├── rag/
│   │   ├── hybrid_retriever.py # 混合检索（向量+BM25+RRF融合）
│   │   ├── vectorstore.py      # ChromaDB 向量存储
│   │   ├── bm25_store.py       # BM25 倒排索引（懒加载重建）
│   │   ├── embeddings.py       # SentenceTransformer 嵌入模型
│   │   ├── loader.py           # 文档加载（Markdown/PDF/TXT）
│   │   ├── splitter.py         # 文本分块
│   │   └── indexer.py          # 索引管理器
│   ├── services/
│   │   └── session_manager.py  # 会话持久化（JSON + UTF-8 BOM）
│   └── models/
│       └── schemas.py          # Pydantic 请求/响应模型
├── frontend/
│   └── app.py                  # Streamlit 前端应用
├── evaluation/
│   ├── eval_dataset.py         # 评估数据集
│   └── run_eval.py             # RAGAS 评估脚本
├── tests/
│   ├── test_api.py             # API 模块测试
│   ├── test_rag.py             # RAG 模块测试
│   └── test_agent.py           # Agent 模块测试
├── data/
│   ├── docs/                   # 文档库（按项目分目录）
│   │   ├── general/            # 本项目部署与配置指南
│   │   ├── general-knowledge/  # 通用技术知识文档
│   │   └── 项目A/              # 业务项目文档
│   ├── chroma_db/              # ChromaDB 持久化数据
│   ├── bm25_index/             # BM25 索引文件
│   └── model_cache/            # HuggingFace 模型缓存
├── Dockerfile                  # 后端容器
├── Dockerfile.frontend         # 前端容器
├── docker-compose.yml          # 编排配置
├── requirements.txt            # Python 依赖
├── .env.example                # 环境变量模板
├── start_backend.bat           # Windows 后端启动脚本
└── start_services.bat          # Windows 一键启动脚本
```

## 快速开始

### 环境要求

- Python 3.10+
- Windows / Linux / macOS
- 至少 4 核 CPU、8GB 内存（纯 CPU 推理）

### 1. 克隆项目

```bash
git clone <repository-url>
cd tech-doc-qa-assistant
```

### 2. 创建虚拟环境并安装依赖

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的 LLM API Key（至少配置一种方案）：

```ini
# 方案 A：SiliconFlow 中转平台（推荐，国内可访问）
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-你的API-Key
DEEPSEEK_BASE_URL=https://api.siliconflow.cn/v1
LLM_MODEL=deepseek-ai/DeepSeek-V3

# 方案 B：DeepSeek 官方 API
# DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
# LLM_MODEL=deepseek-chat

# 方案 C：Ollama 本地模型（完全离线）
# LLM_PROVIDER=ollama
# OLLAMA_BASE_URL=http://localhost:11434
# LLM_MODEL=qwen2.5:7b
```

> 详细配置指南请参考 `data/docs/general/AI模型配置指南.md`

### 4. 启动服务

**方式一：分别启动（开发模式）**

```bash
# 终端 1 — 启动后端
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 终端 2 — 启动前端
python -m streamlit run frontend/app.py --server.port 8501
```

**方式二：一键启动（Windows）**

```bat
start_services.bat
```

**方式三：Docker 部署**

```bash
docker-compose up -d
```

### 5. 访问应用

| 服务 | 地址 |
|------|------|
| 前端界面 | http://localhost:8501 |
| 后端 API | http://localhost:8000 |
| API 文档 (Swagger) | http://localhost:8000/docs |
| 健康检查 | http://localhost:8000/health |

> 首次启动需要加载 Embedding 模型（约 100MB），耗时 10-15 秒属正常现象。

## 核心特性

### 混合检索（Hybrid Search）

并行执行向量检索和关键词检索，通过 RRF（Reciprocal Rank Fusion）算法融合排序：

- **向量检索**（ChromaDB）：语义相似性匹配，理解同义词和意图
- **关键词检索**（BM25 + jieba 分词）：精确匹配技术术语、函数名、配置项
- **RRF 融合**：`score = α × vector_score + (1-α) × bm25_score`，α=0.3 偏向关键词

### 项目级文档隔离

知识库按目录组织，检索时自动识别用户意图中的项目名称：

```
data/docs/
├── general/              # 本项目部署文档
├── general-knowledge/    # 通用技术知识
├── 项目A/                # 业务项目A文档
└── greenhouse-simulator/ # 业务项目B文档
```

识别优先级：查询含项目名 > 自身指代 > 使用说明 > 全库检索

### ReAct Agent 工作流

```
用户问题 → Agent 推理 → 调用 rag_search → 获取知识库文档
                                              │
                                    ┌─────────┴─────────┐
                                    │ 命中 → LLM 生成回答 │
                                    │ 未命中 → web_search │
                                    │         → 互联网兜底 │
                                    └────────────────────┘
```

最多 3 轮工具调用，避免无限循环。

### SSE 流式输出

前端实时显示 LLM 输出的每个 token，同时推送工具调用状态（如"正在调用 rag_search..."），用户体验流畅。

### 会话持久化

对话记录以 JSON 文件持久化存储（UTF-8 BOM 编码），刷新页面或重启服务后历史对话不丢失。

## API 速览

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/chat` | 同步聊天（阻塞等待完整响应） |
| `POST` | `/api/chat/stream` | SSE 流式聊天（实时输出） |
| `POST` | `/api/sessions` | 创建新会话 |
| `GET` | `/api/sessions` | 列出所有会话 |
| `GET` | `/api/sessions/{id}` | 获取会话详情 |
| `DELETE` | `/api/sessions/{id}` | 删除会话 |
| `GET` | `/api/documents/projects` | 获取项目列表 |
| `POST` | `/api/documents/upload` | 上传单个文档 |
| `POST` | `/api/documents/upload-batch` | 批量上传文档 |
| `POST` | `/api/documents/upload-directory` | 上传整个项目目录 |
| `GET` | `/api/documents/list` | 获取已索引文档列表 |
| `DELETE` | `/api/documents/{filename}` | 删除文档 |
| `POST` | `/api/documents/reindex` | 重建索引 |
| `POST` | `/api/documents/cleanup` | 清理孤儿索引 |
| `GET` | `/health` | 健康检查 |

## 运行测试

```bash
pytest tests/ -v
```

## 运行 RAG 评估

```bash
python -m evaluation.run_eval
```

评估指标包括：忠实度（Faithfulness）、答案相关性（Answer Relevancy）、上下文精确率（Context Precision）、上下文召回率（Context Recall）。

## License

MIT
