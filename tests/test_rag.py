"""RAG 模块测试"""
import pytest

def test_rag_module_import():
    """测试 RAG 模块能正常导入"""
    from app.rag import loader, splitter, embeddings, vectorstore, bm25_store, hybrid_retriever, indexer
    assert loader is not None
    assert splitter is not None
    assert embeddings is not None
    assert vectorstore is not None
    assert bm25_store is not None
    assert hybrid_retriever is not None
    assert indexer is not None

def test_hybrid_search():
    """测试混合检索功能"""
    from app.rag.hybrid_retriever import hybrid_search
    results = hybrid_search("测试查询", top_k=3)
    assert isinstance(results, list)