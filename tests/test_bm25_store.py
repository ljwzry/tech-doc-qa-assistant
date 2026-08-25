# -*- coding: utf-8 -*-
"""BM25Store 单元测试 — 覆盖增删改查/懒重建/持久化"""
import pytest
import os
from unittest.mock import patch


@pytest.fixture
def isolated_bm25(tmp_path):
    """创建一个使用临时目录的 BM25Store 实例"""
    from app.rag.bm25_store import BM25Store
    with patch("app.rag.bm25_store.BM25_PERSIST_DIR", str(tmp_path)):
        with patch("app.rag.bm25_store.BM25_PERSIST_FILE", str(tmp_path / "bm25_index.pkl")):
            store = BM25Store()
            yield store


class TestAddDocuments:
    """测试文档添加"""

    def test_add_single_document(self, isolated_bm25):
        docs = [{"text": "Vue.js 是渐进式框架", "metadata": {"source_file": "vue.md", "project": "general-knowledge"}}]
        count = isolated_bm25.add_documents(docs)
        assert count == 1

    def test_add_multiple_documents(self, isolated_bm25):
        docs = [
            {"text": "Git 常用命令", "metadata": {"source_file": "git.md", "project": "general-knowledge"}},
            {"text": "Python 基础教程", "metadata": {"source_file": "python.md", "project": "general-knowledge"}},
            {"text": "React 组件开发", "metadata": {"source_file": "react.md", "project": "general-knowledge"}},
        ]
        count = isolated_bm25.add_documents(docs)
        assert count == 3

    def test_add_empty_list(self, isolated_bm25):
        count = isolated_bm25.add_documents([])
        assert count == 0


class TestSearch:
    """测试搜索功能"""

    def test_search_returns_results(self, isolated_bm25):
        docs = [
            {"text": "Docker container deployment guide for production", "metadata": {"source_file": "docker.md", "project": "general-knowledge"}},
            {"text": "Vue.js frontend development components", "metadata": {"source_file": "vue.md", "project": "general-knowledge"}},
            {"text": "React hooks and state management tutorial", "metadata": {"source_file": "react.md", "project": "general-knowledge"}},
        ]
        isolated_bm25.add_documents(docs)
        results = isolated_bm25.search("docker deployment", top_k=2)
        assert len(results) > 0
        assert "docker" in results[0]["text"].lower()

    def test_search_empty_corpus_returns_empty(self, isolated_bm25):
        results = isolated_bm25.search("test query", top_k=5)
        assert results == []

    def test_search_case_insensitive(self, isolated_bm25):
        """验证大小写不敏感"""
        docs = [
            {"text": "Python is a great programming language for beginners", "metadata": {"source_file": "py.md", "project": "test"}},
            {"text": "JavaScript framework comparison and analysis", "metadata": {"source_file": "js.md", "project": "test"}},
            {"text": "Go language concurrency patterns guide", "metadata": {"source_file": "go.md", "project": "test"}},
        ]
        isolated_bm25.add_documents(docs)
        # 用小写搜索大写内容
        results_lower = isolated_bm25.search("python", top_k=1)
        # 用大写搜索小写内容
        results_upper = isolated_bm25.search("PYTHON", top_k=1)
        assert len(results_lower) > 0
        assert len(results_upper) > 0

    def test_search_returns_metadata(self, isolated_bm25):
        docs = [
            {"text": "Test metadata retrieval in this document about API design", "metadata": {"source_file": "test.md", "project": "projectA"}},
            {"text": "Database optimization index strategies", "metadata": {"source_file": "db.md", "project": "projectB"}},
            {"text": "Security authentication and authorization guide", "metadata": {"source_file": "sec.md", "project": "projectC"}},
        ]
        isolated_bm25.add_documents(docs)
        results = isolated_bm25.search("test metadata api", top_k=1)
        assert len(results) > 0
        assert results[0]["metadata"]["source_file"] == "test.md"
        assert results[0]["metadata"]["project"] == "projectA"

    def test_search_top_k_limits_results(self, isolated_bm25):
        docs = [
            {"text": f"文档内容{i} 测试", "metadata": {"source_file": f"file{i}.md", "project": "test"}}
            for i in range(10)
        ]
        isolated_bm25.add_documents(docs)
        results = isolated_bm25.search("测试", top_k=3)
        assert len(results) <= 3


class TestDelete:
    """测试删除功能"""

    def test_delete_by_source(self, isolated_bm25):
        docs = [
            {"text": "Vue 组件化", "metadata": {"source_file": "vue.md", "project": "test"}},
            {"text": "React Hooks", "metadata": {"source_file": "react.md", "project": "test"}},
        ]
        isolated_bm25.add_documents(docs)
        deleted = isolated_bm25.delete_by_source("vue.md")
        assert deleted == 1
        # 确认删除后搜索不到
        results = isolated_bm25.search("Vue 组件化", top_k=5)
        assert all(r["metadata"]["source_file"] != "vue.md" for r in results)

    def test_delete_by_project(self, isolated_bm25):
        docs = [
            {"text": "文档A", "metadata": {"source_file": "a.md", "project": "项目A"}},
            {"text": "文档B", "metadata": {"source_file": "b.md", "project": "项目A"}},
            {"text": "文档C", "metadata": {"source_file": "c.md", "project": "项目B"}},
        ]
        isolated_bm25.add_documents(docs)
        deleted = isolated_bm25.delete_by_project("项目A")
        assert deleted == 2

    def test_delete_nonexistent_source_returns_zero(self, isolated_bm25):
        docs = [{"text": "测试", "metadata": {"source_file": "exists.md", "project": "test"}}]
        isolated_bm25.add_documents(docs)
        deleted = isolated_bm25.delete_by_source("nonexistent.md")
        assert deleted == 0

    def test_delete_from_empty_store_returns_zero(self, isolated_bm25):
        deleted = isolated_bm25.delete_by_source("anything.md")
        assert deleted == 0


class TestLazyRebuild:
    """测试懒重建机制"""

    def test_delete_marks_dirty_not_immediate_rebuild(self, isolated_bm25):
        """删除后应标记为 dirty，但不立即重建"""
        docs = [
            {"text": "测试懒重建", "metadata": {"source_file": "lazy.md", "project": "test"}},
        ]
        isolated_bm25.add_documents(docs)
        isolated_bm25.delete_by_source("lazy.md")
        assert isolated_bm25._dirty is True

    def test_search_triggers_rebuild_when_dirty(self, isolated_bm25):
        """搜索时应触发懒重建"""
        docs = [
            {"text": "测试懒重建触发", "metadata": {"source_file": "lazy.md", "project": "test"}},
        ]
        isolated_bm25.add_documents(docs)
        isolated_bm25.delete_by_source("lazy.md")
        assert isolated_bm25._dirty is True
        # 搜索应触发重建并清除 dirty 标记
        isolated_bm25.search("测试", top_k=1)
        assert isolated_bm25._dirty is False


class TestPersistence:
    """测试持久化"""

    def test_save_to_disk(self, isolated_bm25, tmp_path):
        docs = [{"text": "持久化测试", "metadata": {"source_file": "persist.md", "project": "test"}}]
        isolated_bm25.add_documents(docs)
        assert (tmp_path / "bm25_index.pkl").exists()

    def test_load_from_disk(self, tmp_path):
        """验证新实例能从磁盘加载"""
        from app.rag.bm25_store import BM25Store
        with patch("app.rag.bm25_store.BM25_PERSIST_DIR", str(tmp_path)):
            with patch("app.rag.bm25_store.BM25_PERSIST_FILE", str(tmp_path / "bm25_index.pkl")):
                store1 = BM25Store()
                store1.add_documents([
                    {"text": "跨实例加载测试", "metadata": {"source_file": "cross.md", "project": "test"}}
                ])

                store2 = BM25Store()
                assert len(store2.corpus) == 1
                assert store2.corpus[0] == "跨实例加载测试"
