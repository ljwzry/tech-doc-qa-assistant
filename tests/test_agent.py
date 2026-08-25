"""Agent 模块测试"""
import pytest

def test_agent_module_import():
    """测试 Agent 模块能正常导入"""
    from app.agent import state, tools, nodes, graph, prompts
    assert state is not None
    assert tools is not None
    assert nodes is not None
    assert graph is not None
    assert prompts is not None

def test_build_graph():
    """测试构建 LangGraph"""
    from app.agent.graph import build_graph
    compiled_graph = build_graph()
    assert compiled_graph is not None