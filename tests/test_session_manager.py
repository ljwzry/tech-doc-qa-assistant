# -*- coding: utf-8 -*-
"""SessionManager 单元测试 — 覆盖创建/保存/读取/删除/持久化全流程"""
import pytest
import json
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock


@pytest.fixture
def isolated_manager(tmp_path):
    """创建一个使用临时目录的 SessionManager 实例，测试间互不干扰"""
    from app.services.session_manager import SessionManager
    with patch("app.services.session_manager.SESSION_STORAGE_PATH", str(tmp_path)):
        mgr = SessionManager()
        yield mgr
        # 清理临时会话
        for sid in list(mgr.sessions.keys()):
            mgr.delete_session(sid)


class TestCreateSession:
    """测试会话创建"""

    def test_create_session_returns_id(self, isolated_manager):
        sid = isolated_manager.create_session()
        assert sid is not None
        assert len(sid) == 8  # uuid[:8]

    def test_create_session_initialized_empty(self, isolated_manager):
        sid = isolated_manager.create_session()
        session = isolated_manager.get_session(sid)
        assert session is not None
        assert session["messages"] == []
        assert session["project"] == ""
        assert "created_at" in session

    def test_create_multiple_sessions_have_different_ids(self, isolated_manager):
        sid1 = isolated_manager.create_session()
        sid2 = isolated_manager.create_session()
        assert sid1 != sid2


class TestSaveMessage:
    """测试消息保存"""

    def test_save_user_message(self, isolated_manager):
        sid = isolated_manager.create_session()
        isolated_manager.save_message(sid, "user", "你好世界")
        msgs = isolated_manager.get_messages(sid)
        assert len(msgs) == 1
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "你好世界"

    def test_save_multiple_messages_preserves_order(self, isolated_manager):
        sid = isolated_manager.create_session()
        isolated_manager.save_message(sid, "user", "第一条")
        isolated_manager.save_message(sid, "assistant", "回复1")
        isolated_manager.save_message(sid, "user", "第二条")
        msgs = isolated_manager.get_messages(sid)
        assert len(msgs) == 3
        assert msgs[0]["content"] == "第一条"
        assert msgs[1]["content"] == "回复1"
        assert msgs[2]["content"] == "第二条"

    def test_save_message_with_project(self, isolated_manager):
        sid = isolated_manager.create_session()
        isolated_manager.save_message(sid, "user", "测试", project="项目A")
        session = isolated_manager.get_session(sid)
        assert session["project"] == "项目A"

    def test_save_message_to_nonexistent_session_auto_creates(self, isolated_manager):
        """保存消息到不存在的会话ID时，应自动创建会话"""
        # 使用一个不存在的 session_id
        isolated_manager.save_message("autocreate", "user", "自动创建测试")
        session = isolated_manager.get_session("autocreate")
        assert session is not None
        assert len(session["messages"]) == 1

    def test_save_chinese_message_no_garbled(self, isolated_manager):
        """验证中文消息不会乱码"""
        test_text = "测试中文编码：你好世界！Vue.js 组件化开发 🎉"
        sid = isolated_manager.create_session()
        isolated_manager.save_message(sid, "user", test_text)
        msgs = isolated_manager.get_messages(sid)
        assert msgs[0]["content"] == test_text
        # 确保没有替换字符
        assert "\ufffd" not in msgs[0]["content"]


class TestDeleteSession:
    """测试会话删除"""

    def test_delete_session_removes_from_memory(self, isolated_manager):
        sid = isolated_manager.create_session()
        isolated_manager.save_message(sid, "user", "测试")
        isolated_manager.delete_session(sid)
        assert isolated_manager.get_session(sid) is None
        assert isolated_manager.get_messages(sid) == []

    def test_delete_session_removes_file(self, isolated_manager, tmp_path):
        sid = isolated_manager.create_session()
        isolated_manager.save_message(sid, "user", "测试删除文件")
        filepath = os.path.join(str(tmp_path), f"{sid}.json")
        assert os.path.exists(filepath)
        isolated_manager.delete_session(sid)
        assert not os.path.exists(filepath)

    def test_delete_nonexistent_session_no_error(self, isolated_manager):
        """删除不存在的会话不应抛异常"""
        isolated_manager.delete_session("nonexistent_id")


class TestListSessions:
    """测试会话列表"""

    def test_list_empty_when_no_sessions(self, isolated_manager):
        sessions = isolated_manager.list_sessions()
        assert sessions == []

    def test_list_sessions_returns_all(self, isolated_manager):
        sid1 = isolated_manager.create_session()
        sid2 = isolated_manager.create_session()
        sessions = isolated_manager.list_sessions()
        ids = [s["session_id"] for s in sessions]
        assert sid1 in ids
        assert sid2 in ids

    def test_list_sessions_includes_messages(self, isolated_manager):
        sid = isolated_manager.create_session()
        isolated_manager.save_message(sid, "user", "测试消息")
        sessions = isolated_manager.list_sessions()
        target = [s for s in sessions if s["session_id"] == sid][0]
        assert len(target["messages"]) == 1


class TestPersistence:
    """测试会话持久化（文件读写）"""

    def test_session_saved_to_file(self, isolated_manager, tmp_path):
        sid = isolated_manager.create_session()
        isolated_manager.save_message(sid, "user", "持久化测试")
        filepath = os.path.join(str(tmp_path), f"{sid}.json")
        assert os.path.exists(filepath)

    def test_session_file_is_utf8_bom(self, isolated_manager, tmp_path):
        """验证文件使用 utf-8-sig（BOM）编码"""
        sid = isolated_manager.create_session()
        isolated_manager.save_message(sid, "user", "中文编码测试")
        filepath = os.path.join(str(tmp_path), f"{sid}.json")
        with open(filepath, "rb") as f:
            raw = f.read(3)
        # UTF-8 BOM: EF BB BF
        assert raw == b'\xef\xbb\xbf'

    def test_session_file_content_is_valid_json(self, isolated_manager, tmp_path):
        sid = isolated_manager.create_session()
        isolated_manager.save_message(sid, "user", "JSON验证")
        filepath = os.path.join(str(tmp_path), f"{sid}.json")
        with open(filepath, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        assert "messages" in data
        assert len(data["messages"]) == 1

    def test_reload_sessions_from_disk(self, tmp_path):
        """验证新建 SessionManager 能从磁盘恢复会话"""
        from app.services.session_manager import SessionManager
        with patch("app.services.session_manager.SESSION_STORAGE_PATH", str(tmp_path)):
            mgr1 = SessionManager()
            sid = mgr1.create_session()
            mgr1.save_message(sid, "user", "跨实例恢复测试")

            # 新建第二个实例，应能加载已有会话
            mgr2 = SessionManager()
            session = mgr2.get_session(sid)
            assert session is not None
            assert len(session["messages"]) == 1
            assert session["messages"][0]["content"] == "跨实例恢复测试"
