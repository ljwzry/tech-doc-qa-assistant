import jieba
import pickle
import os
import threading
from rank_bm25 import BM25Okapi
from typing import List, Dict, Any

BM25_PERSIST_DIR = "./data/bm25_index"
BM25_PERSIST_FILE = os.path.join(BM25_PERSIST_DIR, "bm25_index.pkl")

class BM25Store:
    def __init__(self):
        self.corpus, self.metadatas, self.tokenized, self.bm25 = [], [], [], None
        # 脏标记：增删操作置为 True，搜索时若为 True 才重建索引
        # 避免每次增删都立即重建（大数据量下重建耗时显著）
        self._dirty = False
        self._lock = threading.Lock()
        self._load_from_disk()

    def add_documents(self, documents: List[Dict]) -> int:
        """批量追加文档。仅在循环结束后重建一次索引（非每条重建）"""
        with self._lock:
            count = 0
            for doc in documents:
                self.corpus.append(doc["text"])
                self.metadatas.append(doc["metadata"])
                # 转为小写进行分词，确保大小写不敏感
                self.tokenized.append(list(jieba.cut(doc["text"].lower())))
                count += 1
            # 批量追加完成后一次性重建索引
            self._rebuild_index()
            self._save_to_disk()
            return count

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        with self._lock:
            # 懒重建：仅当存在未应用的增删时才重建
            if self._dirty:
                self._rebuild_index()
                self._dirty = False
            if not self.bm25:
                return []
        # 转为小写进行搜索，确保大小写不敏感
        query_tokens = list(jieba.cut(query.lower()))
        scores = self.bm25.get_scores(query_tokens)
        top_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        return [{"text": self.corpus[i], "metadata": self.metadatas[i], "score": float(scores[i])}
                for i in top_idx if scores[i] > 0]

    def delete_by_source(self, source_file: str) -> int:
        """根据源文件名删除文档（标记为脏，不立即重建）"""
        with self._lock:
            if not self.corpus:
                return 0
            # 找到需要删除的索引
            to_delete = []
            for i, meta in enumerate(self.metadatas):
                if meta.get("source_file") == source_file:
                    to_delete.append(i)
            # 逆序删除，保持索引正确
            for i in sorted(to_delete, reverse=True):
                del self.corpus[i]
                del self.metadatas[i]
                del self.tokenized[i]
            # 标记为脏，下次搜索时懒重建
            self._dirty = True
            self._save_to_disk()
            return len(to_delete)

    def delete_by_project(self, project: str) -> int:
        """根据项目名称删除所有该项目的文档（标记为脏，不立即重建）"""
        with self._lock:
            if not self.corpus:
                return 0
            # 找到需要删除的索引
            to_delete = []
            for i, meta in enumerate(self.metadatas):
                if meta.get("project") == project:
                    to_delete.append(i)
            # 逆序删除，保持索引正确
            for i in sorted(to_delete, reverse=True):
                del self.corpus[i]
                del self.metadatas[i]
                del self.tokenized[i]
            # 标记为脏，下次搜索时懒重建
            self._dirty = True
            self._save_to_disk()
            return len(to_delete)

    def _rebuild_index(self):
        """重建 BM25 索引（内部方法，调用方需持有锁）"""
        if self.corpus:
            self.bm25 = BM25Okapi(self.tokenized)
        else:
            self.bm25 = None

    def _save_to_disk(self):
        """持久化到磁盘"""
        os.makedirs(BM25_PERSIST_DIR, exist_ok=True)
        data = {
            "corpus": self.corpus,
            "metadatas": self.metadatas,
            "tokenized": self.tokenized
        }
        with open(BM25_PERSIST_FILE, "wb") as f:
            pickle.dump(data, f)

    def _load_from_disk(self):
        """从磁盘加载"""
        if os.path.exists(BM25_PERSIST_FILE):
            try:
                with open(BM25_PERSIST_FILE, "rb") as f:
                    data = pickle.load(f)
                    self.corpus = data.get("corpus", [])
                    self.metadatas = data.get("metadatas", [])
                    self.tokenized = data.get("tokenized", [])
                    if self.corpus:
                        self._rebuild_index()
                        self._dirty = False
            except Exception:
                # 加载失败，使用空索引
                self.corpus, self.metadatas, self.tokenized, self.bm25 = [], [], [], None
                self._dirty = False

_bm25 = BM25Store()
def get_bm25_store(): return _bm25
