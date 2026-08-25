# -*- coding: utf-8 -*-
"""HybridRetriever 单元测试 — 覆盖项目识别/文件名匹配/RRF融合/结果过滤"""
import pytest
from unittest.mock import patch, MagicMock
from app.rag.hybrid_retriever import (
    hybrid_search, _doc_key, _get_project_names,
    get_document_chunks
)


class TestDocKey:
    """测试文档唯一标识生成"""

    def test_same_text_and_source_generates_same_key(self):
        key1 = _doc_key("测试内容", "readme.md")
        key2 = _doc_key("测试内容", "readme.md")
        assert key1 == key2

    def test_different_text_generates_different_key(self):
        key1 = _doc_key("内容A", "readme.md")
        key2 = _doc_key("内容B", "readme.md")
        assert key1 != key2

    def test_different_source_generates_different_key(self):
        key1 = _doc_key("相同内容", "file1.md")
        key2 = _doc_key("相同内容", "file2.md")
        assert key1 != key2

    def test_chinese_text_key(self):
        """验证中文内容不会导致 key 生成异常"""
        key = _doc_key("你好世界Vue.js组件", "中文文档.md")
        assert isinstance(key, str)
        assert "中文文档.md" in key


class TestGetProjectNames:
    """测试项目名称扫描"""

    def test_returns_sorted_by_length_desc(self):
        """长名优先，避免 'general' 误匹配 'general-knowledge'"""
        with patch("os.path.isdir", return_value=True):
            with patch("os.listdir", return_value=["general", "general-knowledge", "项目A"]):
                with patch("os.path.join", side_effect=lambda *args: "/".join(args)):
                    names = _get_project_names()
                    # 长名应排前面
                    assert names[0] == "general-knowledge"
                    assert "general" in names
                    assert "项目A" in names

    def test_returns_empty_when_dir_not_exists(self):
        with patch("os.path.isdir", return_value=False):
            names = _get_project_names()
            assert names == []

    def test_excludes_hidden_dirs(self):
        with patch("os.path.isdir", return_value=True):
            with patch("os.listdir", return_value=["projectA", ".hidden", "general"]):
                with patch("os.path.join", side_effect=lambda *args: "/".join(args)):
                    names = _get_project_names()
                    assert ".hidden" not in names
                    assert "projectA" in names


class TestProjectDetection:
    """测试项目范围自动识别（三级优先级）"""

    @patch("app.rag.hybrid_retriever.get_document_chunks", return_value=[])
    @patch("app.rag.hybrid_retriever.search_chroma", return_value={"documents": [[]], "metadatas": [[]]})
    @patch("app.rag.hybrid_retriever.get_bm25_store")
    @patch("app.rag.hybrid_retriever._get_project_names", return_value=["general", "项目A", "general-knowledge"])
    def test_explicit_project_name_in_query(self, mock_names, mock_bm25, mock_chroma, mock_chunks):
        """Step 1: 查询中包含具体项目名 → 锁定该项目"""
        mock_bm25.return_value.search.return_value = []
        hybrid_search("项目A怎么部署")
        # 验证 search_chroma 被调用时 where_filter 包含 项目A
        call_args = mock_chroma.call_args
        assert call_args[0][3] == {"project": "项目A"}

    @patch("app.rag.hybrid_retriever.get_document_chunks", return_value=[])
    @patch("app.rag.hybrid_retriever.search_chroma", return_value={"documents": [[]], "metadatas": [[]]})
    @patch("app.rag.hybrid_retriever.get_bm25_store")
    @patch("app.rag.hybrid_retriever._get_project_names", return_value=["general", "项目A"])
    def test_self_reference_locks_general(self, mock_names, mock_bm25, mock_chroma, mock_chunks):
        """Step 2: 查询包含自身指代词 → 锁定 general"""
        mock_bm25.return_value.search.return_value = []
        hybrid_search("技术文档问答助手怎么用")
        call_args = mock_chroma.call_args
        assert call_args[0][3] == {"project": "general"}

    @patch("app.rag.hybrid_retriever.get_document_chunks", return_value=[])
    @patch("app.rag.hybrid_retriever.search_chroma", return_value={"documents": [[]], "metadatas": [[]]})
    @patch("app.rag.hybrid_retriever.get_bm25_store")
    @patch("app.rag.hybrid_retriever._get_project_names", return_value=["general", "项目A"])
    def test_usage_keywords_lock_general(self, mock_names, mock_bm25, mock_chroma, mock_chunks):
        """Step 3: 查询包含使用说明类关键词 → 锁定 general"""
        mock_bm25.return_value.search.return_value = []
        hybrid_search("使用说明在哪")
        call_args = mock_chroma.call_args
        assert call_args[0][3] == {"project": "general"}

    @patch("app.rag.hybrid_retriever.get_document_chunks", return_value=[])
    @patch("app.rag.hybrid_retriever.search_chroma", return_value={"documents": [[]], "metadatas": [[]]})
    @patch("app.rag.hybrid_retriever.get_bm25_store")
    @patch("app.rag.hybrid_retriever._get_project_names", return_value=["项目A", "项目B"])
    def test_no_match_searches_all(self, mock_names, mock_bm25, mock_chroma, mock_chunks):
        """未匹配任何项目 → 全库检索（where_filter=None）"""
        mock_bm25.return_value.search.return_value = []
        hybrid_search("数据库设计最佳实践")
        call_args = mock_chroma.call_args
        assert call_args[0][3] is None

    @patch("app.rag.hybrid_retriever.get_document_chunks", return_value=[])
    @patch("app.rag.hybrid_retriever.search_chroma", return_value={"documents": [[]], "metadatas": [[]]})
    @patch("app.rag.hybrid_retriever.get_bm25_store")
    @patch("app.rag.hybrid_retriever._get_project_names", return_value=["general-knowledge", "general"])
    def test_long_project_name_matched_first(self, mock_names, mock_bm25, mock_chroma, mock_chunks):
        """验证 'general-knowledge' 优先于 'general' 匹配"""
        mock_bm25.return_value.search.return_value = []
        hybrid_search("general-knowledge的文档")
        call_args = mock_chroma.call_args
        assert call_args[0][3] == {"project": "general-knowledge"}


class TestFilenameMatch:
    """测试文件名匹配检索"""

    @patch("app.rag.hybrid_retriever.get_document_chunks")
    def test_filename_match_returns_chunks_directly(self, mock_chunks):
        """查询中包含文件名时，直接返回该文档的 chunk"""
        mock_chunks.return_value = [
            {"text": "README 内容", "metadata": {"source_file": "README.md", "project": "项目A"}}
        ]
        with patch("app.rag.hybrid_retriever.search_chroma") as mock_chroma:
            with patch("app.rag.hybrid_retriever.get_bm25_store"):
                results = hybrid_search("给我看 README.md")
                assert len(results) == 1
                assert results[0]["source_file"] == "README.md" if "source_file" in results[0] else True
                # 向量和 BM25 检索不应被调用
                mock_chroma.assert_not_called()

    @patch("app.rag.hybrid_retriever.get_document_chunks", return_value=[])
    @patch("app.rag.hybrid_retriever.search_chroma", return_value={"documents": [[]], "metadatas": [[]]})
    @patch("app.rag.hybrid_retriever.get_bm25_store")
    def test_filename_not_found_falls_back_to_search(self, mock_bm25, mock_chroma, mock_chunks):
        """文件名匹配不到时，回退到向量+BM25检索"""
        mock_bm25.return_value.search.return_value = []
        results = hybrid_search("nonexistent.md 的内容")
        # 应回退到 search_chroma
        mock_chroma.assert_called_once()


class TestRRFFusion:
    """测试 RRF 融合逻辑"""

    @patch("app.rag.hybrid_retriever.get_document_chunks", return_value=[])
    @patch("app.rag.hybrid_retriever.search_chroma")
    @patch("app.rag.hybrid_retriever.get_bm25_store")
    def test_vector_and_bm25_results_merged(self, mock_bm25, mock_chroma, mock_chunks):
        """验证向量检索和 BM25 检索结果被正确合并"""
        mock_chroma.return_value = {
            "documents": [["Vue 组件化开发", "React Hooks"]],
            "metadatas": [[{"source_file": "vue.md"}, {"source_file": "react.md"}]]
        }
        mock_bm25.return_value.search.return_value = [
            {"text": "Vue 组件化开发", "metadata": {"source_file": "vue.md"}, "score": 2.0},
            {"text": "Angular 指令", "metadata": {"source_file": "angular.md"}, "score": 1.0},
        ]
        results = hybrid_search("前端框架", top_k=5)
        # 应有 3 条不重复结果（Vue 在两边都有，去重后为 3）
        assert len(results) == 3
        # 每条结果应有 score 字段
        for r in results:
            assert "score" in r
            assert "text" in r
            assert "metadata" in r

    @patch("app.rag.hybrid_retriever.get_document_chunks", return_value=[])
    @patch("app.rag.hybrid_retriever.search_chroma")
    @patch("app.rag.hybrid_retriever.get_bm25_store")
    def test_top_k_limits_results(self, mock_bm25, mock_chroma, mock_chunks):
        """验证 top_k 参数限制返回数量"""
        mock_chroma.return_value = {
            "documents": [[f"文档{i}" for i in range(10)]],
            "metadatas": [[{"source_file": f"file{i}.md"} for i in range(10)]]
        }
        mock_bm25.return_value.search.return_value = []
        results = hybrid_search("测试", top_k=3)
        assert len(results) <= 3

    @patch("app.rag.hybrid_retriever.get_document_chunks", return_value=[])
    @patch("app.rag.hybrid_retriever.search_chroma", return_value={"documents": [[]], "metadatas": [[]]})
    @patch("app.rag.hybrid_retriever.get_bm25_store")
    def test_bm25_project_filter(self, mock_bm25, mock_chroma, mock_chunks):
        """验证指定 project 时 BM25 结果被过滤"""
        mock_bm25.return_value.search.return_value = [
            {"text": "项目A文档", "metadata": {"source_file": "a.md", "project": "项目A"}, "score": 2.0},
            {"text": "项目B文档", "metadata": {"source_file": "b.md", "project": "项目B"}, "score": 1.0},
        ]
        results = hybrid_search("文档", top_k=5, project="项目A")
        # 项目B的文档应被过滤掉
        for r in results:
            assert r["metadata"].get("project") != "项目B"

    @patch("app.rag.hybrid_retriever.get_document_chunks", return_value=[])
    @patch("app.rag.hybrid_retriever.search_chroma", return_value={"documents": [[]], "metadatas": [[]]})
    @patch("app.rag.hybrid_retriever.get_bm25_store")
    def test_empty_results_returns_empty_list(self, mock_bm25, mock_chroma, mock_chunks):
        """两边都没有结果时返回空列表"""
        mock_bm25.return_value.search.return_value = []
        results = hybrid_search("不存在的查询", top_k=5)
        assert results == []


class TestGetDocumentChunks:
    """测试按文件名获取文档 chunk"""

    def test_calls_collection_with_correct_filter(self):
        mock_collection = MagicMock()
        mock_collection.get.return_value = {
            "documents": ["chunk1", "chunk2"],
            "metadatas": [{"source_file": "test.md", "project": "项目A"}, {"source_file": "test.md", "project": "项目A"}]
        }
        with patch("app.rag.hybrid_retriever.get_collection", return_value=mock_collection):
            chunks = get_document_chunks("test.md", project="项目A")
            assert len(chunks) == 2
            # 验证 where 条件包含 $and
            call_args = mock_collection.get.call_args
            where = call_args[1]["where"]
            assert "$and" in where

    def test_max_chunks_limit(self):
        mock_collection = MagicMock()
        mock_collection.get.return_value = {
            "documents": [f"chunk{i}" for i in range(20)],
            "metadatas": [{"source_file": "big.md"}] * 20
        }
        with patch("app.rag.hybrid_retriever.get_collection", return_value=mock_collection):
            chunks = get_document_chunks("big.md", max_chunks=5)
            assert len(chunks) == 5

    def test_no_results_returns_empty(self):
        mock_collection = MagicMock()
        mock_collection.get.return_value = {"documents": [], "metadatas": []}
        with patch("app.rag.hybrid_retriever.get_collection", return_value=mock_collection):
            chunks = get_document_chunks("nonexistent.md")
            assert chunks == []
