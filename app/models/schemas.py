from pydantic import BaseModel
from typing import List, Optional, Dict

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    message_history: Optional[List[Dict[str, str]]] = None
    project: Optional[str] = None  # 项目名称，指定后只检索该项目的文档