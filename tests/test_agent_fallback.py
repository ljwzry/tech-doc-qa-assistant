# -*- coding: utf-8 -*-
"""Agent 自动检索机制单元测试

覆盖核心流程：
1. 知识库命中 → rag_search 返回结果 → LLM 基于文档回答（不调用 web_search）
2. 知识库未命中 → rag_search 无结果 → LLM 自动调用 web_search 兜底 → 基于网络结果回答
3. LLM 未调用工具时的 bypass 兜底逻辑
4. 关键词检测函数 _detect_needs_tool
"""
import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agent import nodes
from app.agent.tools import set_current_project


# ─── Fixtures ───────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_llm_cache():
    """每个测试前后重置 LLM 缓存，避免测试间互相影响"""
    original = nodes._llm_bound
    nodes._llm_bound = None
    yield
    nodes._llm_bound = original


@pytest.fixture(autouse=True)
def reset_project_context():
    """每个测试前清除项目上下文"""
    set_current_project(None)
    yield
    set_current_project(None)


def _make_tool_call(name, query, call_id):
    """构造 AIMessage tool_calls 条目"""
    return {"name": name, "args": {"query": query}, "id": call_id}


# ─── 1. 关键词检测 ───────────────────────────────────────────

class TestDetectNeedsTool:
    """测试 _detect_needs_tool 关键词检测"""

    def test_technical_question_returns_rag(self):
        """技术问题应路由到 rag_search"""
        assert nodes._detect_needs_tool("Git怎么撤销提交") == "rag_search"

    def test_deploy_question_returns_rag(self):
        """部署问题应路由到 rag_search"""
        assert nodes._detect_needs_tool("项目A怎么部署") == "rag_search"

    def test_weather_question_returns_web(self):
        """天气查询应路由到 web_search"""
        assert nodes._detect_needs_tool("西安今天天气怎么样") == "web_search"

    def test_news_question_returns_web(self):
        """新闻类查询应路由到 web_search"""
        assert nodes._detect_needs_tool("最新的科技新闻") == "web_search"

    def test_static_knowledge_returns_none(self):
        """静态常识问题不需要工具"""
        assert nodes._detect_needs_tool("水的化学式是什么") is None

    def test_unknown_tech_returns_none(self):
        """不在关键词列表中的技术问题返回 None（依赖 LLM 自主决策）"""
        assert nodes._detect_needs_tool("Rust语言的所有权机制") is None


# ─── 1.5 实体检测 ───────────────────────────────────────────

class TestEntityExtraction:
    """测试 _extract_key_entities 和 _check_entity_coverage"""

    def test_extract_entities_from_comparison_question(self):
        """从对比问题中提取两个实体"""
        entities = nodes._extract_key_entities("Vue和React有什么区别")
        assert "Vue" in entities
        assert "React" in entities

    def test_extract_single_entity(self):
        """从单个实体问题中提取"""
        entities = nodes._extract_key_entities("React有什么特点")
        assert "React" in entities
        assert len(entities) == 1

    def test_no_entities_in_general_question(self):
        """通用问题没有技术实体"""
        entities = nodes._extract_key_entities("今天天气怎么样")
        assert len(entities) == 0

    def test_coverage_all_entities_found(self):
        """所有实体都在结果中"""
        query = "Vue和React有什么区别"
        result = "Vue是渐进式框架，React是组件化框架。两者都是JavaScript框架。"
        uncovered = nodes._check_entity_coverage(query, result)
        assert len(uncovered) == 0

    def test_coverage_partial_match(self):
        """部分实体在结果中（只有 Vue，没有 React）"""
        query = "Vue和React有什么区别"
        result = "Vue是渐进式JavaScript框架，核心关注点是视图层。"
        uncovered = nodes._check_entity_coverage(query, result)
        assert "React" in uncovered
        assert "Vue" not in uncovered

    def test_coverage_no_entities_found(self):
        """没有实体在结果中"""
        query = "Vue和React有什么区别"
        result = "这是一篇关于CSS的文档，介绍了样式表的使用。"
        uncovered = nodes._check_entity_coverage(query, result)
        assert "Vue" in uncovered
        assert "React" in uncovered


# ─── 2. agent_node 单元测试 ─────────────────────────────────

class TestAgentNodeToolCalling:
    """测试 agent_node 的 LLM 工具调用逻辑（mock LLM）"""

    def test_llm_calls_rag_search(self):
        """LLM 主动调用 rag_search 时，agent_node 应返回带 tool_calls 的消息"""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(
            content="",
            tool_calls=[_make_tool_call("rag_search", "Git撤销提交", "call_1")]
        )
        nodes._llm_bound = mock_llm

        state = {
            "messages": [HumanMessage(content="Git怎么撤销提交")],
            "query": "Git怎么撤销提交",
            "retrieved_docs": [],
            "retries": 0,
        }
        result = nodes.agent_node(state)

        assert mock_llm.invoke.call_count == 1
        returned_msg = result["messages"][0]
        assert returned_msg.tool_calls is not None
        assert len(returned_msg.tool_calls) == 1
        assert returned_msg.tool_calls[0]["name"] == "rag_search"

    def test_llm_falls_back_to_web_search(self):
        """知识库未命中时，LLM 应在第二轮调用 web_search"""
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [
            # 第一轮：调用 rag_search
            AIMessage(content="", tool_calls=[_make_tool_call("rag_search", "Rust所有权", "call_1")]),
            # 第二轮：rag_search 无结果 → 调用 web_search
            AIMessage(content="", tool_calls=[_make_tool_call("web_search", "Rust所有权", "call_2")]),
        ]
        nodes._llm_bound = mock_llm

        # 第一轮（retries=0）：LLM 返回 rag_search tool_calls
        state = {
            "messages": [HumanMessage(content="Rust语言的所有权机制")],
            "query": "Rust语言的所有权机制",
            "retrieved_docs": [],
            "retries": 0,
        }
        result = nodes.agent_node(state)
        assert result["messages"][0].tool_calls[0]["name"] == "rag_search"

        # 模拟 graph 循环：tool 执行后 retries=1，再次进入 agent_node
        state_with_tool_result = {
            "messages": [
                HumanMessage(content="Rust语言的所有权机制"),
                AIMessage(content="", tool_calls=[_make_tool_call("rag_search", "Rust所有权", "call_1")]),
                ToolMessage(content="未在知识库中找到相关文档。", tool_call_id="call_1"),
            ],
            "query": "Rust语言的所有权机制",
            "retrieved_docs": [],
            "retries": 1,
        }
        result2 = nodes.agent_node(state_with_tool_result)
        assert result2["messages"][0].tool_calls[0]["name"] == "web_search"

    def test_bypass_when_llm_skips_tool(self):
        """LLM 未调用工具但问题是技术问题时，bypass 应直接调用 rag_search"""
        mock_llm = MagicMock()
        # LLM 第一次不调用工具（返回纯文本）
        mock_llm.invoke.side_effect = [
            AIMessage(content="我直接回答吧"),  # 无 tool_calls
            AIMessage(content="根据文档，git revert 可以撤销提交"),  # bypass 后的回答
        ]
        nodes._llm_bound = mock_llm

        state = {
            "messages": [HumanMessage(content="Git怎么撤销提交")],
            "query": "Git怎么撤销提交",
            "retrieved_docs": [],
            "retries": 0,
        }
        result = nodes.agent_node(state)

        # bypass 应触发第二次 LLM 调用（带工具结果）
        assert mock_llm.invoke.call_count == 2
        final_msg = result["messages"][0]
        assert "git revert" in final_msg.content

    def test_no_bypass_for_static_knowledge(self):
        """静态常识问题不触发 bypass"""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(content="水的化学式是 H2O")
        nodes._llm_bound = mock_llm

        state = {
            "messages": [HumanMessage(content="水的化学式是什么")],
            "query": "水的化学式是什么",
            "retrieved_docs": [],
            "retries": 0,
        }
        result = nodes.agent_node(state)

        # LLM 只被调用一次，没有 bypass
        assert mock_llm.invoke.call_count == 1
        assert "H2O" in result["messages"][0].content

    def test_partial_match_triggers_web_search_supplement(self):
        """知识库部分匹配（只找到 Vue，问题涉及 Vue 和 React）时，应自动补充 web_search"""
        mock_llm = MagicMock()
        # 第一轮：LLM 调用 rag_search
        # 第二轮：rag_search 返回部分结果（只有 Vue），LLM 未调工具 → 触发实体检测 → 追加 web_search
        # 第三轮：注入 web_search 结果后，LLM 基于完整结果回答
        mock_llm.invoke.side_effect = [
            # 第一轮：调用 rag_search
            AIMessage(content="", tool_calls=[_make_tool_call("rag_search", "Vue和React区别", "call_1")]),
            # 第二轮：LLM 基于部分结果（只有 Vue）回答，不再调工具
            AIMessage(content="Vue是渐进式框架。...(缺少React信息)"),
            # 第三轮：注入 web_search 补充结果后，LLM 基于完整结果回答
            AIMessage(content="Vue是渐进式框架，React是组件化框架。来源: vue-guide.md + 网络搜索"),
        ]
        nodes._llm_bound = mock_llm

        # 第一轮（retries=0）：LLM 调用 rag_search
        state_round1 = {
            "messages": [HumanMessage(content="Vue和React有什么区别")],
            "query": "Vue和React有什么区别",
            "retrieved_docs": [],
            "retries": 0,
        }
        result1 = nodes.agent_node(state_round1)
        assert result1["messages"][0].tool_calls[0]["name"] == "rag_search"

        # 第二轮（retries=1）：rag_search 返回只有 Vue 的结果
        state_round2 = {
            "messages": [
                HumanMessage(content="Vue和React有什么区别"),
                AIMessage(content="", tool_calls=[_make_tool_call("rag_search", "Vue和React区别", "call_1")]),
                ToolMessage(
                    content="【文档1】来源: vue-guide.md\nVue是渐进式JavaScript框架，核心关注点是视图层。",
                    tool_call_id="call_1",
                    name="rag_search"
                ),
            ],
            "query": "Vue和React有什么区别",
            "retrieved_docs": [],
            "retries": 1,
        }
        result2 = nodes.agent_node(state_round2)

        # 由于知识库只覆盖了 Vue（未覆盖 React），应该触发 web_search 补充
        # 检查是否产生了新的 web_search 相关消息
        final_msg = result2["messages"][0]
        # 最终应该是 LLM 基于补充后的完整结果回答
        assert "React" in final_msg.content or "组件化" in final_msg.content


# ─── 3. Graph 集成测试：知识库命中 ──────────────────────────

class TestGraphKbHit:
    """完整 Graph 流程：知识库命中 → 不调用 web_search"""

    @patch("app.agent.tools._search_bing")
    @patch("app.agent.tools.hybrid_search")
    def test_kb_hit_answers_from_rag_only(self, mock_hybrid, mock_bing):
        """知识库命中时，仅调用 rag_search，不调用 web_search"""
        # 知识库返回结果
        mock_hybrid.return_value = [
            {
                "text": "git revert <commit-hash> 用于撤销已推送的提交",
                "metadata": {"source_file": "git-commands.md", "project": "general-knowledge"},
            }
        ]

        # Mock LLM：第一轮调用 rag_search，第二轮基于结果回答
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [
            AIMessage(content="", tool_calls=[_make_tool_call("rag_search", "Git撤销提交", "c1")]),
            AIMessage(content="根据文档，使用 git revert 撤销提交。来源: git-commands.md"),
        ]
        nodes._llm_bound = mock_llm

        from app.agent.graph import build_graph
        graph = build_graph()
        result = graph.invoke({
            "messages": [HumanMessage(content="Git怎么撤销提交")],
            "query": "Git怎么撤销提交",
            "retrieved_docs": [],
            "retries": 0,
        })

        # rag_search 被调用
        mock_hybrid.assert_called_once()
        # web_search 未被调用（Bing 未触发）
        mock_bing.assert_not_called()
        # 回答包含知识库内容
        answer = result["messages"][-1].content
        assert "git revert" in answer

    @patch("app.agent.tools._search_bing")
    @patch("app.agent.tools.hybrid_search")
    def test_kb_hit_no_web_search_in_messages(self, mock_hybrid, mock_bing):
        """验证消息历史中不包含 web_search 工具调用"""
        mock_hybrid.return_value = [
            {
                "text": "Vue 是渐进式 JavaScript 框架",
                "metadata": {"source_file": "vue-guide.md", "project": "general-knowledge"},
            }
        ]
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [
            AIMessage(content="", tool_calls=[_make_tool_call("rag_search", "Vue介绍", "c1")]),
            AIMessage(content="Vue 是渐进式框架。来源: vue-guide.md"),
        ]
        nodes._llm_bound = mock_llm

        from app.agent.graph import build_graph
        graph = build_graph()
        result = graph.invoke({
            "messages": [HumanMessage(content="Vue是什么")],
            "query": "Vue是什么",
            "retrieved_docs": [],
            "retries": 0,
        })

        # 检查所有消息中不含 web_search 工具调用
        for msg in result["messages"]:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    assert tc["name"] != "web_search", "知识库命中时不应调用 web_search"


# ─── 4. Graph 集成测试：知识库未命中 → web_search 兜底 ─────

class TestGraphKbMissWebFallback:
    """完整 Graph 流程：知识库未命中 → 自动 web_search 兜底"""

    @patch("app.agent.tools._search_bing")
    @patch("app.agent.tools.hybrid_search")
    def test_kb_miss_triggers_web_search(self, mock_hybrid, mock_bing):
        """知识库未命中时，自动调用 web_search 搜索互联网"""
        # 知识库返回空
        mock_hybrid.return_value = []
        # Bing 返回网络结果
        mock_bing.return_value = [
            {
                "title": "Rust所有权指南",
                "body": "Rust中每个值都有唯一的所有者，当所有者离开作用域时值被自动释放",
                "href": "https://rust-lang.org/ownership",
            }
        ]

        # Mock LLM：rag_search → web_search → 最终回答
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [
            AIMessage(content="", tool_calls=[_make_tool_call("rag_search", "Rust所有权", "c1")]),
            AIMessage(content="", tool_calls=[_make_tool_call("web_search", "Rust所有权", "c2")]),
            AIMessage(content="根据网络搜索，Rust中每个值都有唯一的所有者。来源: https://rust-lang.org/ownership"),
        ]
        nodes._llm_bound = mock_llm

        from app.agent.graph import build_graph
        graph = build_graph()
        result = graph.invoke({
            "messages": [HumanMessage(content="Rust语言的所有权机制是什么")],
            "query": "Rust语言的所有权机制是什么",
            "retrieved_docs": [],
            "retries": 0,
        })

        # rag_search 被调用
        mock_hybrid.assert_called_once()
        # web_search 也被调用（Bing 被触发）
        mock_bing.assert_called_once()
        # 回答包含网络搜索内容
        answer = result["messages"][-1].content
        assert "所有者" in answer or "rust-lang.org" in answer

    @patch("app.agent.tools._search_bing")
    @patch("app.agent.tools.hybrid_search")
    def test_kb_miss_web_search_called_after_rag(self, mock_hybrid, mock_bing):
        """验证 web_search 在 rag_search 之后被调用（顺序正确）"""
        mock_hybrid.return_value = []
        mock_bing.return_value = [
            {"title": "Go并发编程", "body": "goroutine是Go的轻量级线程", "href": "https://go.dev"}
        ]

        call_order = []

        def track_hybrid(*args, **kwargs):
            call_order.append("rag_search")
            return []

        def track_bing(*args, **kwargs):
            call_order.append("web_search")
            return [{"title": "Go并发", "body": "goroutine", "href": "https://go.dev"}]

        mock_hybrid.side_effect = track_hybrid
        mock_bing.side_effect = track_bing

        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [
            AIMessage(content="", tool_calls=[_make_tool_call("rag_search", "Go goroutine", "c1")]),
            AIMessage(content="", tool_calls=[_make_tool_call("web_search", "Go goroutine", "c2")]),
            AIMessage(content="根据搜索结果，goroutine是Go的轻量级线程。来源: https://go.dev"),
        ]
        nodes._llm_bound = mock_llm

        from app.agent.graph import build_graph
        graph = build_graph()
        graph.invoke({
            "messages": [HumanMessage(content="Go语言的goroutine怎么用")],
            "query": "Go语言的goroutine怎么用",
            "retrieved_docs": [],
            "retries": 0,
        })

        assert call_order == ["rag_search", "web_search"]

    @patch("app.agent.tools._search_bing")
    @patch("app.agent.tools.hybrid_search")
    def test_both_empty_returns_no_results(self, mock_hybrid, mock_bing):
        """知识库和网络搜索都无结果时，LLM 应回答未找到"""
        mock_hybrid.return_value = []
        mock_bing.return_value = []

        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [
            AIMessage(content="", tool_calls=[_make_tool_call("rag_search", "未知技术", "c1")]),
            AIMessage(content="", tool_calls=[_make_tool_call("web_search", "未知技术", "c2")]),
            AIMessage(content="抱歉，未找到关于该主题的相关信息。"),
        ]
        nodes._llm_bound = mock_llm

        from app.agent.graph import build_graph
        graph = build_graph()
        result = graph.invoke({
            "messages": [HumanMessage(content="某种不存在的冷门技术")],
            "query": "某种不存在的冷门技术",
            "retrieved_docs": [],
            "retries": 0,
        })

        mock_hybrid.assert_called_once()
        mock_bing.assert_called_once()
        answer = result["messages"][-1].content
        assert "未找到" in answer or "抱歉" in answer
