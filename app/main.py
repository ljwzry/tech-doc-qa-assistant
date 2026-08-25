import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api.chat import router as chat_router
from app.api.documents import router as doc_router
from app.config import settings

# 配置日志级别
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时预加载模型与索引，避免首次请求等待"""
    import time
    t0 = time.time()
    logger.info("开始预加载资源...")

    # 1. Embedding 模型（最耗时，优先加载）
    try:
        from app.rag.embeddings import get_embeddings
        get_embeddings()
        logger.info(f"[1/4] Embedding 模型已加载 ({time.time()-t0:.1f}s)")
    except Exception as e:
        logger.warning(f"[1/4] Embedding 模型预加载失败（将在首次请求时懒加载）: {e}")

    t1 = time.time()
    # 2. Chroma 向量集合
    try:
        from app.rag.vectorstore import get_collection
        get_collection()
        logger.info(f"[2/4] Chroma 集合已加载 ({time.time()-t1:.1f}s)")
    except Exception as e:
        logger.warning(f"[2/4] Chroma 预加载失败: {e}")

    t2 = time.time()
    # 3. BM25 索引
    try:
        from app.rag.bm25_store import get_bm25_store
        get_bm25_store()
        logger.info(f"[3/4] BM25 索引已加载 ({time.time()-t2:.1f}s)")
    except Exception as e:
        logger.warning(f"[3/4] BM25 预加载失败: {e}")

    t3 = time.time()
    # 4. LLM 连接初始化
    try:
        from app.agent.nodes import get_llm
        get_llm()
        logger.info(f"[4/4] LLM 连接已初始化 ({time.time()-t3:.1f}s)")
    except Exception as e:
        logger.warning(f"[4/4] LLM 预加载失败（将在首次请求时懒加载）: {e}")

    logger.info(f"资源预加载完成，总耗时 {time.time()-t0:.1f}s")
    yield
    logger.info("服务关闭")

app = FastAPI(title="TechDoc QA Assistant", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"])

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """API 鉴权中间件，仅当 AUTH_ENABLED=true 时生效"""
    if not settings.auth_enabled:
        response = await call_next(request)
        return response

    # /health 端点免鉴权
    if request.url.path == "/health":
        response = await call_next(request)
        return response

    auth_header = request.headers.get("authorization", "")
    expected = settings.api_key

    if not auth_header:
        return JSONResponse(
            status_code=401,
            content={"detail": "缺少 Authorization 头"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer" or parts[1] != expected:
        return JSONResponse(
            status_code=401,
            content={"detail": "API Key 无效"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    response = await call_next(request)
    return response

app.include_router(chat_router)
app.include_router(doc_router)

@app.get("/health")
async def health(): return {"status":"ok"}