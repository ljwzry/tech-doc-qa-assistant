"""会话管理服务 - 存储和恢复对话历史"""

import uuid
import json
import os
import time
from typing import Dict, List, Optional

SESSION_STORAGE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "sessions")

class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, Dict] = {}
        self._ensure_storage_dir()
        self._load_sessions()
    
    def _ensure_storage_dir(self):
        os.makedirs(SESSION_STORAGE_PATH, exist_ok=True)
    
    def _load_sessions(self):
        """从文件加载会话"""
        try:
            for filename in os.listdir(SESSION_STORAGE_PATH):
                if filename.endswith(".json"):
                    session_id = filename[:-5]
                    filepath = os.path.join(SESSION_STORAGE_PATH, filename)
                    with open(filepath, "r", encoding="utf-8-sig") as f:
                        self.sessions[session_id] = json.load(f)
        except Exception:
            pass
    
    def _save_session(self, session_id: str):
        """保存会话到文件（强制 UTF-8 编码 + BOM，防止 Windows GBK 环境乱码）"""
        if session_id in self.sessions:
            filepath = os.path.join(SESSION_STORAGE_PATH, f"{session_id}.json")
            # 使用 utf-8-sig（带 BOM）确保 Windows 下 PowerShell/记事本都能正确识别编码
            with open(filepath, "w", encoding="utf-8-sig") as f:
                json.dump(self.sessions[session_id], f, ensure_ascii=False, indent=2)
    
    def create_session(self) -> str:
        """创建新会话"""
        session_id = str(uuid.uuid4())[:8]  # 使用短ID
        self.sessions[session_id] = {
            "messages": [],
            "project": "",
            "created_at": time.time()
        }
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """获取会话"""
        return self.sessions.get(session_id)
    
    def save_message(self, session_id: str, role: str, content: str, project: str = ""):
        """保存消息"""
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "messages": [],
                "project": "",
                "created_at": time.time()
            }
        
        self.sessions[session_id]["messages"].append({
            "role": role,
            "content": content
        })
        if project:
            self.sessions[session_id]["project"] = project
        
        self._save_session(session_id)
    
    def get_messages(self, session_id: str) -> List[Dict]:
        """获取会话消息"""
        session = self.sessions.get(session_id)
        return session["messages"] if session else []
    
    def delete_session(self, session_id: str):
        """删除会话"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            # 删除文件
            filepath = os.path.join(SESSION_STORAGE_PATH, f"{session_id}.json")
            if os.path.exists(filepath):
                os.remove(filepath)
    
    def list_sessions(self) -> List[Dict]:
        """列出所有会话"""
        return [
            {"session_id": sid, **data}
            for sid, data in self.sessions.items()
        ]

# 全局会话管理器实例
session_manager = SessionManager()
