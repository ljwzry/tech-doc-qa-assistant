import json
import asyncio
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse
from app.models.schemas import ChatRequest
from app.agent.graph import build_graph
from app.agent.tools import set_current_project
from app.services.session_manager import session_manager
from app.utils import success_response, error_response
from langchain_core.messages import HumanMessage, AIMessage
from typing import Optional, List

router = APIRouter(prefix="/api", tags=["chat"])
_graph = None

def get_graph():
    global _graph
    if _graph is None: _graph = build_graph()
    return _graph

def build_messages(request: ChatRequest):
    """构建 LangChain 消息列表，包含历史对话"""
    messages = []
    
    # 如果有 session_id，从会话管理器获取历史消息
    if request.session_id:
        session_messages = session_manager.get_messages(request.session_id)
        for msg in session_messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
    
    # 如果还有额外的 message_history，追加
    if request.message_history:
        for msg in request.message_history:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "human":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
    
    messages.append(HumanMessage(content=request.message))
    return messages

@router.post("/chat")
async def chat(request: ChatRequest):
    graph = get_graph()
    messages = build_messages(request)
    # 设置当前检索的项目范围
    set_current_project(request.project)
    # graph.invoke 是同步阻塞操作（含 LLM API 请求 + 向量检索），
    # 放到线程池中执行，避免阻塞 FastAPI 主事件循环
    result = await asyncio.to_thread(graph.invoke, {
        "messages": messages,
        "query": request.message,
        "retrieved_docs": [],
        "retries": 0,
    })

    # 保存消息到会话
    if request.session_id:
        session_manager.save_message(request.session_id, "user", request.message, request.project)
        session_manager.save_message(request.session_id, "assistant", result["messages"][-1].content)

    # 同时返回统一格式和顶层 answer 字段，保持向后兼容
    answer = result["messages"][-1].content
    return {
        "code": 0,
        "message": "操作成功",
        "answer": answer,
        "session_id": request.session_id,
        "data": {
            "answer": answer,
            "session_id": request.session_id
        }
    }

@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    graph = get_graph()
    messages = build_messages(request)
    # 设置当前检索的项目范围
    set_current_project(request.project)

    full_response = ""

    async def event_gen():
        nonlocal full_response
        try:
            # 尝试流式输出
            has_token = False
            try:
                async for event in graph.astream_events(
                    input={"messages": messages,
                        "query": request.message, "retrieved_docs": [], "retries": 0}, version="v2"):
                    kind = event["event"]
                    if kind == "on_chat_model_stream":
                        chunk = event["data"].get("chunk", {})
                        if hasattr(chunk, 'content') and chunk.content:
                            has_token = True
                            full_response += chunk.content
                            yield f"data: {json.dumps({'type': 'token', 'content': chunk.content}, ensure_ascii=False)}\n\n"
                    elif kind == "on_tool_start":
                        yield f'data: {json.dumps({"type": "tool_call", "content": "正在调用 " + event["name"]}, ensure_ascii=False)}\n\n'
            except Exception as stream_err:
                # 流式失败（如 "No generations found in stream"），fallback 到同步
                if not has_token:
                    import logging
                    logging.getLogger(__name__).warning(f"[stream] 流式失败，fallback 到同步: {stream_err}")
                    yield f'data: {json.dumps({"type": "tool_call", "content": "正在检索中..."}, ensure_ascii=False)}\n\n'
                    result = await asyncio.to_thread(graph.invoke, {
                        "messages": messages,
                        "query": request.message,
                        "retrieved_docs": [],
                        "retries": 0,
                    })
                    full_response = result["messages"][-1].content
                    yield f"data: {json.dumps({'type': 'token', 'content': full_response}, ensure_ascii=False)}\n\n"

            yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"

            # 保存消息到会话
            if request.session_id and full_response:
                session_manager.save_message(request.session_id, "user", request.message, request.project)
                session_manager.save_message(request.session_id, "assistant", full_response)
        except Exception as e:
            import traceback
            error_msg = str(e)
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'content': error_msg}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream; charset=utf-8",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive",
                 "Content-Type": "text/event-stream; charset=utf-8"})

@router.get("/sessions")
async def list_sessions():
    """列出所有会话"""
    sessions = session_manager.list_sessions()
    return success_response(sessions)

@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """获取会话详情"""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return success_response(session)

@router.post("/sessions")
async def create_session():
    """创建新会话"""
    session_id = session_manager.create_session()
    return success_response({"session_id": session_id})

@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除会话"""
    session_manager.delete_session(session_id)
    return success_response(message="会话删除成功")