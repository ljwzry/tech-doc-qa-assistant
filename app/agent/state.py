from typing import Annotated, List
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    query: str
    retrieved_docs: List[dict]
    retries: int