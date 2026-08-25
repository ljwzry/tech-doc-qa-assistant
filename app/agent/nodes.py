import logging
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, AIMessage
from app.agent.state import AgentState
from app.agent.tools import ALL_TOOLS, rag_search, web_search
from app.config import settings
from app.agent.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# 缓存 LLM 实例，避免每次调用都重新创建（减少连接初始化开销）
_llm = None
_llm_bound = None

def get_llm():
    global _llm
    if _llm is None:
        if settings.llm_provider == "ollama":
            from langchain_ollama import ChatOllama
            _llm = ChatOllama(
                base_url=settings.ollama_base_url,
                model=settings.llm_model,
                timeout=120,
            )
        else:
            from langchain_openai import ChatOpenAI
            _llm = ChatOpenAI(
                model=settings.llm_model,
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
                max_retries=3,
                timeout=60,
                max_tokens=4096,
                temperature=0.1,
            )
    return _llm


def _detect_needs_tool(user_msg: str) -> str | None:
    """检测用户消息是否需要搜索，返回需要的工具名或 None"""
    web_keywords = ["天气", "新闻", "股价", "最新", "今天", "现在", "实时", "汇率", "体育", "比分", "天气预报"]
    rag_keywords = ["部署", "配置", "安装", "架构", "代码", "API", "接口", "数据库", "项目", "文档",
                    "Git", "Vue", "React", "Python", "Java", "Redis", "Docker", "Kubernetes",
                    "MQTT", "MQTT", "greenhouse", "技术文档", "问答助手"]
    
    if any(kw in user_msg for kw in web_keywords):
        return "web_search"
    if any(kw in user_msg for kw in rag_keywords):
        return "rag_search"
    return None


def _direct_tool_search(user_msg: str, tool_name: str, project: str | None = None) -> str:
    """直接调用工具搜索，不依赖 LLM tool calling"""
    if tool_name == "web_search":
        return web_search.invoke({"query": user_msg, "max_results": 3})
    elif tool_name == "rag_search":
        return rag_search.invoke({"query": user_msg, "top_k": 5})
    return ""


def _extract_key_entities(query: str) -> list[str]:
    """从用户问题中提取关键技术实体（框架名、技术术语等）"""
    import re
    # 已知的技术实体列表（按长度排序，优先匹配长的）
    known_entities = [
        "JavaScript", "TypeScript", "Python", "Java", "React", "Vue", "Angular",
        "Node.js", "Node", "Django", "Flask", "FastAPI", "Spring", "SpringBoot",
        "Redis", "MySQL", "PostgreSQL", "MongoDB", "Kafka", "RabbitMQ",
        "Docker", "Kubernetes", "AWS", "Azure", "GCP",
        "Git", "Linux", "Windows", "macOS", "Nginx",
        "CSS", "HTML", "Sass", "Less", "Tailwind",
        "Redux", "Vuex", "Pinia", "GraphQL", "REST",
        "TensorFlow", "PyTorch", "Pandas", "NumPy",
        "微服务", "分布式", "高并发", "大数据", "人工智能", "机器学习",
        "组件化", "响应式", "虚拟DOM", "JSX", "Hooks", "Composition API",
        "Vite", "Webpack", "Rollup", "Babel",
    ]
    # 按长度排序（长的优先匹配，避免 React 匹配到 Reac 后剩下 t）
    known_entities.sort(key=len, reverse=True)
    
    found = []
    query_lower = query.lower()
    for entity in known_entities:
        if entity.lower() in query_lower:
            found.append(entity)
    
    # 提取引号内的内容作为补充
    quoted = re.findall(r'[""](.*?)[""]', query)
    for q in quoted:
        if q not in found and len(q) >= 2:
            found.append(q)
    
    return found


def _check_entity_coverage(query: str, search_result: str) -> list[str]:
    """检查搜索结果是否覆盖了用户问题中的关键实体，返回未覆盖的实体列表"""
    entities = _extract_key_entities(query)
    if not entities:
        return []
    
    result_lower = search_result.lower()
    uncovered = []
    for entity in entities:
        # 检查实体名或其常见变体是否出现在结果中
        variants = [entity.lower()]
        # 添加常见变体
        if entity == "React":
            variants.extend(["react", "reactjs", "react.js"])
        elif entity == "Vue":
            variants.extend(["vue", "vuejs", "vue.js"])
        
        if not any(v in result_lower for v in variants):
            uncovered.append(entity)
    
    return uncovered


def agent_node(state: AgentState) -> dict:
    """Agent 推理节点"""
    global _llm_bound
    if _llm_bound is None:
        _llm_bound = get_llm().bind_tools(ALL_TOOLS)
    
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    response = _llm_bound.invoke(messages)
    
    # 调试日志
    last_user_msg = ""
    for msg in reversed(state["messages"]):
        if msg.type == "human":
            last_user_msg = msg.content
            break
    logger.info(f"[agent_node] msg={last_user_msg!r}, tool_calls={bool(response.tool_calls)}, retries={state.get('retries', 0)}")
    
    # 如果 LLM 没有调用工具，但问题需要搜索 → 直接调用工具
    if not response.tool_calls and state.get("retries", 0) == 0:
        tool_name = _detect_needs_tool(last_user_msg)
        if tool_name:
            logger.info(f"[agent_node] 触发自动工具调用: {tool_name}")
            tool_result = _direct_tool_search(last_user_msg, tool_name)
            logger.info(f"[agent_node] 工具结果长度: {len(tool_result)}")
            
            # 检查实体覆盖情况
            uncovered = _check_entity_coverage(last_user_msg, tool_result)
            if uncovered and tool_name == "rag_search":
                logger.info(f"[agent_node] 知识库未覆盖实体: {uncovered}，触发 web_search 补充")
                # 用未覆盖的实体构造补充查询
                supplement_query = f"{uncovered[0]} {last_user_msg}"
                web_result = _direct_tool_search(supplement_query, "web_search")
                logger.info(f"[agent_node] web_search 补充结果长度: {len(web_result)}")
                # 合并结果
                combined_result = f"""【知识库检索结果】
{tool_result}

【互联网补充搜索结果（补充: {', '.join(uncovered)}）】
{web_result}"""
                tool_result = combined_result
            
            # 用工具结果重新让 LLM 回答
            tool_msg = ToolMessage(content=tool_result, tool_call_id="auto_tool_call")
            final_messages = messages + [
                AIMessage(content="", tool_calls=[{"name": tool_name, "args": {"query": last_user_msg}, "id": "auto_tool_call"}]),
                tool_msg
            ]
            response = _llm_bound.invoke(final_messages)
    
    # 检测 rag_search 结果是否只覆盖了部分实体，如果是则追加 web_search
    if state.get("retries", 0) >= 1 and not response.tool_calls:
        # 从历史中找到最近的 rag_search 结果
        rag_result = ""
        has_rag_tool = False
        for msg in reversed(state["messages"]):
            if isinstance(msg, ToolMessage) and msg.name == "rag_search":
                rag_result = msg.content
                has_rag_tool = True
                break
        
        if has_rag_tool and rag_result:
            uncovered = _check_entity_coverage(last_user_msg, rag_result)
            if uncovered:
                logger.info(f"[agent_node] 检测到知识库部分匹配，未覆盖实体: {uncovered}，追加 web_search")
                # 构造补充查询
                supplement_query = f"{uncovered[0]} {last_user_msg}"
                web_result = _direct_tool_search(supplement_query, "web_search")
                logger.info(f"[agent_node] web_search 补充结果长度: {len(web_result)}")
                
                # 将补充结果注入历史
                web_tool_msg = ToolMessage(
                    content=f"【互联网补充搜索结果】\n{web_result}",
                    tool_call_id="auto_web_supplement",
                    name="web_search"
                )
                supplement_ai = AIMessage(
                    content="",
                    tool_calls=[{"name": "web_search", "args": {"query": supplement_query}, "id": "auto_web_supplement"}]
                )
                retry_messages = messages + [supplement_ai, web_tool_msg]
                response = _llm_bound.invoke(retry_messages)
    
    # 如果 LLM 回答暗示"无法获取"但之前有工具结果 → 用更强提示重试
    if not response.tool_calls and state.get("retries", 0) >= 1:
        answer_text = response.content or ""
        failure_indicators = ["无法获取", "未能找到", "无法从", "未能获取", "没有相关"]
        if any(ind in answer_text for ind in failure_indicators):
            # 检查是否有 tool message 在历史中
            has_tool_results = any(
                isinstance(m, ToolMessage) for m in state["messages"]
            )
            if has_tool_results:
                logger.info("[agent_node] 检测到 LLM 拒绝使用搜索结果，强制重试")
                force_msg = SystemMessage(content="""你之前已经获取到了搜索结果，必须基于这些结果回答。
即使结果不完全匹配，也要：
1. 总结已找到的信息
2. 如果是天气查询，给出通用的天气建议
3. 不要说"无法获取"，而是说"根据搜索结果，我找到了以下信息：...\"""")
                retry_messages = [force_msg] + state["messages"]
                response = _llm_bound.invoke(retry_messages)
    
    return {"messages": [response]}
