# -*- coding: utf-8 -*-
"""Agent Tools 单元测试 — 覆盖 rag_search/web_search/项目上下文/结果格式化"""
import pytest
from unittest.mock import patch, MagicMock
from app.agent.tools import (
    rag_search, web_search, set_current_project,
    _current_project, _format_results, _search_baidu
)


class TestSetCurrentProject:
    """测试项目上下文设置"""

    def test_set_project(self):
        set_current_project("项目A")
        assert _current_project.get() == "项目A"

    def test_set_none_clears_project(self):
        set_current_project("项目A")
        set_current_project(None)
        assert _current_project.get() is None

    def test_set_empty_string(self):
        set_current_project("")
        assert _current_project.get() == ""


class TestRagSearch:
    """测试 rag_search 工具"""

    @patch("app.agent.tools.hybrid_search")
    def test_returns_not_found_when_no_results(self, mock_search):
        mock_search.return_value = []
        result = rag_search.invoke({"query": "不存在的查询"})
        assert "未在知识库中找到" in result

    @patch("app.agent.tools.hybrid_search")
    def test_returns_not_found_with_project(self, mock_search):
        mock_search.return_value = []
        set_current_project("项目A")
        result = rag_search.invoke({"query": "不存在的查询"})
        assert "项目A" in result
        set_current_project(None)

    @patch("app.agent.tools.hybrid_search")
    def test_returns_formatted_results(self, mock_search):
        mock_search.return_value = [
            {"text": "Vue 是渐进式框架", "metadata": {"source_file": "vue.md", "project": "general-knowledge"}},
            {"text": "Vue 支持组件化", "metadata": {"source_file": "vue.md", "project": "general-knowledge"}},
        ]
        result = rag_search.invoke({"query": "Vue 介绍"})
        assert "[文档1]" in result
        assert "vue.md" in result
        assert "general-knowledge" in result

    @patch("app.agent.tools.hybrid_search")
    def test_merges_chunks_from_same_source(self, mock_search):
        """同一文档的多个 chunk 应合并显示"""
        mock_search.return_value = [
            {"text": "第一部分内容", "metadata": {"source_file": "doc.md", "project": "test"}},
            {"text": "第二部分内容", "metadata": {"source_file": "doc.md", "project": "test"}},
        ]
        result = rag_search.invoke({"query": "测试"})
        # 同一来源应合并为一个文档条目
        assert result.count("[文档1]") == 1
        assert "第一部分内容" in result
        assert "第二部分内容" in result

    @patch("app.agent.tools.hybrid_search")
    def test_multiple_sources_separate_documents(self, mock_search):
        """不同来源的文档应分别显示"""
        mock_search.return_value = [
            {"text": "文档A内容", "metadata": {"source_file": "a.md", "project": "test"}},
            {"text": "文档B内容", "metadata": {"source_file": "b.md", "project": "test"}},
        ]
        result = rag_search.invoke({"query": "测试"})
        assert "[文档1]" in result
        assert "[文档2]" in result

    @patch("app.agent.tools.hybrid_search")
    def test_long_document_truncated(self, mock_search):
        """超过 2000 字符的文档应被截断"""
        long_text = "A" * 3000
        mock_search.return_value = [
            {"text": long_text, "metadata": {"source_file": "big.md", "project": "test"}},
        ]
        result = rag_search.invoke({"query": "测试"})
        assert "内容已截断" in result

    @patch("app.agent.tools.hybrid_search")
    def test_total_chars_limit(self, mock_search):
        """总字符数超过 5000 时应提示更多未显示"""
        mock_search.return_value = [
            {"text": "X" * 2000, "metadata": {"source_file": f"file{i}.md", "project": "test"}}
            for i in range(10)
        ]
        result = rag_search.invoke({"query": "测试"})
        assert "还有更多文档未显示" in result

    @patch("app.agent.tools.hybrid_search")
    def test_uses_current_project_context(self, mock_search):
        """验证 rag_search 使用 contextvars 中的项目上下文"""
        mock_search.return_value = []
        set_current_project("我的项目")
        rag_search.invoke({"query": "测试"})
        mock_search.assert_called_once_with("测试", top_k=5, project="我的项目")
        set_current_project(None)

    @patch("app.agent.tools.hybrid_search")
    def test_chinese_content_no_garbled(self, mock_search):
        """验证中文内容不会乱码"""
        mock_search.return_value = [
            {"text": "你好世界！Vue.js 组件化开发 🎉", "metadata": {"source_file": "中文.md", "project": "测试"}},
        ]
        result = rag_search.invoke({"query": "中文"})
        assert "你好世界" in result
        assert "\ufffd" not in result


class TestFormatResults:
    """测试搜索结果格式化"""

    def test_format_single_result(self):
        results = [{"title": "测试标题", "body": "测试内容", "href": "http://example.com"}]
        formatted = _format_results(results)
        assert "[结果1]" in formatted
        assert "测试标题" in formatted
        assert "测试内容" in formatted
        assert "http://example.com" in formatted

    def test_format_multiple_results(self):
        results = [
            {"title": "标题1", "body": "内容1", "href": "url1"},
            {"title": "标题2", "body": "内容2", "href": "url2"},
        ]
        formatted = _format_results(results)
        assert "[结果1]" in formatted
        assert "[结果2]" in formatted

    def test_format_empty_fields(self):
        results = [{"title": "", "body": "", "href": ""}]
        formatted = _format_results(results)
        assert "[结果1]" in formatted  # 即使字段为空也应格式化

    def test_format_empty_list(self):
        formatted = _format_results([])
        assert formatted == ""


class TestWebSearch:
    """测试 web_search 工具（mock 网络请求）"""

    @patch("app.agent.tools._search_baidu")
    def test_baidu_returns_results(self, mock_baidu):
        mock_baidu.return_value = [
            {"title": "百度结果", "body": "内容", "href": "http://baidu.com"}
        ]
        result = web_search.invoke({"query": "测试"})
        assert "[结果1]" in result
        assert "百度结果" in result

    @patch("app.agent.tools.DDGS")
    @patch("app.agent.tools._search_baidu", return_value=[])
    def test_fallback_to_duckduckgo(self, mock_baidu, mock_ddgs_class):
        mock_ddgs_instance = MagicMock()
        mock_ddgs_class.return_value.__enter__ = MagicMock(return_value=mock_ddgs_instance)
        mock_ddgs_class.return_value.__exit__ = MagicMock(return_value=False)
        mock_ddgs_instance.text.return_value = iter([
            {"title": "DDG结果", "body": "DDG内容", "href": "http://ddg.com"}
        ])
        result = web_search.invoke({"query": "测试"})
        assert "DDG结果" in result

    @patch("app.agent.tools.DDGS")
    @patch("app.agent.tools._search_baidu", side_effect=Exception("网络错误"))
    def test_both_fail_returns_not_found(self, mock_baidu, mock_ddgs_class):
        mock_ddgs_instance = MagicMock()
        mock_ddgs_class.return_value.__enter__ = MagicMock(return_value=mock_ddgs_instance)
        mock_ddgs_class.return_value.__exit__ = MagicMock(return_value=False)
        mock_ddgs_instance.text.side_effect = Exception("DDG也失败")
        result = web_search.invoke({"query": "测试"})
        assert "未找到" in result
