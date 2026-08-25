from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from app.agent.state import AgentState
from app.agent.nodes import agent_node
from app.agent.tools import ALL_TOOLS

MAX_RETRIES = 3

def should_continue(state: AgentState) -> str:
    last = state["messages"][-1]
    if not last.tool_calls: return "end"
    if state.get("retries", 0) >= MAX_RETRIES: return "end"
    return "tools"

def increment_retries(state: AgentState) -> dict:
    """工具执行后递增重试计数器"""
    return {"retries": state.get("retries", 0) + 1}

def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(ALL_TOOLS))
    graph.add_node("increment_retries", increment_retries)
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", "end": END})
    graph.add_edge("tools", "increment_retries")
    graph.add_edge("increment_retries", "agent")
    return graph.compile()