import time
import threading
import os
# 设置完全离线模式，避免访问 HuggingFace 导致超时
# 模型已缓存到本地，无需再访问远程服务器
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

from sentence_transformers import SentenceTransformer
from langchain_core.embeddings import Embeddings
from typing import List
from app.config import settings

class BGEEmbeddings(Embeddings):
    """基于 BGE 系列模型的本地 Embedding，实现 LangChain 接口
    
    优化策略：
    - 使用 BAAI/bge-small-zh 模型（约100MB），适合纯 CPU 环境
    - 启用批处理加速
    - 设置合适的线程数充分利用多核 CPU
    - 使用 HF_ENDPOINT 镜像源解决国内网络问题
    """
    def __init__(self):
        print(f"正在加载 Embedding 模型: {settings.embedding_model} (设备: {settings.embedding_device})")
        print(f"使用镜像源: {os.getenv('HF_ENDPOINT')}")
        start_time = time.time()
        # 使用 huggingface 镜像源加载模型
        # local_files_only=True 确保只使用本地缓存，不访问远程服务器
        self.model = SentenceTransformer(
            settings.embedding_model, 
            device=settings.embedding_device,
            cache_folder="./data/model_cache",
            local_files_only=True
        )
        # CPU 优化配置
        if settings.embedding_device == "cpu":
            # 启用多线程编码，充分利用多核 CPU
            self.model.max_seq_length = 512
            # 设置 PyTorch 线程数为物理核心数
            import torch
            torch.set_num_threads(min(settings.embedding_threads, 8))
        load_time = time.time() - start_time
        print(f"[OK] Embedding 模型加载完成，耗时 {load_time:.2f}s")

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """批量编码文档，启用批处理加速"""
        # 分批处理，避免内存占用过大
        batch_size = 32
        results = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            embeddings = self.model.encode(batch, show_progress_bar=False, batch_size=batch_size)
            results.extend([e.tolist() for e in embeddings])
        return results

    def embed_query(self, text: str) -> List[float]:
        """编码单个查询"""
        return self.model.encode(text, show_progress_bar=False).tolist()

_embeddings = None
_embeddings_lock = threading.Lock()
_embeddings_initialized = False

def initialize_embeddings_async():
    """异步预加载 Embedding 模型，避免首次请求延迟"""
    global _embeddings_initialized
    with _embeddings_lock:
        if not _embeddings_initialized:
            try:
                get_embeddings()
                _embeddings_initialized = True
            except Exception as e:
                print(f"[WARN] 预加载 Embedding 模型失败: {e}")

def get_embeddings():
    global _embeddings
    with _embeddings_lock:
        if _embeddings is None:
            _embeddings = BGEEmbeddings()
    return _embeddings