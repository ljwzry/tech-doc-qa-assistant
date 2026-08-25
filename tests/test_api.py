"""API 模块测试"""
import pytest
from fastapi.testclient import TestClient

def test_api_module_import():
    """测试 API 模块能正常导入"""
    from app.api import chat, documents
    assert chat is not None
    assert documents is not None

def test_health_endpoint():
    """测试健康检查端点"""
    from app.main import app
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}