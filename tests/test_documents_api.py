# -*- coding: utf-8 -*-
"""Documents API 单元测试 — 覆盖上传/列表/删除/项目/重建索引/清理孤儿"""
import pytest
import os
import io
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path):
    """创建 TestClient，mock 掉重型依赖（Embedding 模型/Chroma/BM25/LLM）"""
    with patch("app.rag.embeddings.get_embeddings", return_value=MagicMock()), \
         patch("app.rag.vectorstore.get_collection", return_value=MagicMock()), \
         patch("app.agent.nodes.get_llm", return_value=MagicMock()), \
         patch("app.api.documents.UPLOAD_DIR", str(tmp_path)), \
         patch("app.api.documents.index_file", return_value=1), \
         patch("app.api.documents.chroma_delete_by_source", return_value=0), \
         patch("app.api.documents.get_bm25_store", return_value=MagicMock()):
        from app.main import app
        with TestClient(app) as c:
            yield c


class TestListProjects:
    """测试项目列表 API"""

    def test_list_projects_returns_general_first(self, client, tmp_path):
        os.makedirs(os.path.join(str(tmp_path), "general"), exist_ok=True)
        os.makedirs(os.path.join(str(tmp_path), "项目A"), exist_ok=True)
        response = client.get("/api/documents/projects")
        assert response.status_code == 200
        data = response.json()["data"]
        projects = data["projects"]
        assert "general" in projects
        assert "项目A" in projects

    def test_list_projects_ensures_general_exists(self, client, tmp_path):
        """即使磁盘上没有 general 目录，API 也应返回 general"""
        os.makedirs(os.path.join(str(tmp_path), "项目B"), exist_ok=True)
        response = client.get("/api/documents/projects")
        assert response.status_code == 200
        data = response.json()["data"]
        projects = data["projects"]
        assert "general" in projects

    def test_list_projects_excludes_hidden(self, client, tmp_path):
        os.makedirs(os.path.join(str(tmp_path), ".hidden"), exist_ok=True)
        os.makedirs(os.path.join(str(tmp_path), "visible"), exist_ok=True)
        response = client.get("/api/documents/projects")
        data = response.json()["data"]
        projects = data["projects"]
        assert ".hidden" not in projects


class TestListDocuments:
    """测试文档列表 API"""

    def test_list_empty_when_no_docs(self, client, tmp_path):
        with patch("app.rag.vectorstore.get_collection") as mc:
            mc.return_value.get.return_value = {"metadatas": [], "documents": [], "ids": []}
            response = client.get("/api/documents/list")
            assert response.status_code == 200
            data = response.json()["data"]
            assert data["documents"] == []
            assert data["orphaned"] == []

    def test_list_returns_docs_with_indexed_status(self, client, tmp_path):
        # 创建测试文件
        test_file = os.path.join(str(tmp_path), "general", "test.md")
        os.makedirs(os.path.dirname(test_file), exist_ok=True)
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("# 测试文档")
        with patch("app.rag.vectorstore.get_collection") as mc:
            mc.return_value.get.return_value = {
                "metadatas": [{"source_file": "test.md", "project": "general"}],
                "documents": ["内容"],
                "ids": ["id1"]
            }
            response = client.get("/api/documents/list")
            assert response.status_code == 200
            data = response.json()["data"]
            docs = data["documents"]
            assert len(docs) == 1
            assert docs[0]["filename"] == "test.md"
            assert docs[0]["indexed"] is True

    def test_list_detects_orphaned_indexes(self, client, tmp_path):
        """检测 Chroma 中有但磁盘上没有的孤儿索引"""
        with patch("app.rag.vectorstore.get_collection") as mc:
            mc.return_value.get.return_value = {
                "metadatas": [{"source_file": "deleted.md", "project": "general"}],
                "documents": ["已删除的内容"],
                "ids": ["id1"]
            }
            response = client.get("/api/documents/list")
            data = response.json()["data"]
            orphaned = data["orphaned"]
            assert len(orphaned) == 1
            assert orphaned[0]["filename"] == "deleted.md"

    def test_list_filter_by_project(self, client, tmp_path):
        os.makedirs(os.path.join(str(tmp_path), "项目A"), exist_ok=True)
        with open(os.path.join(str(tmp_path), "项目A", "a.md"), "w", encoding="utf-8") as f:
            f.write("A")
        os.makedirs(os.path.join(str(tmp_path), "项目B"), exist_ok=True)
        with open(os.path.join(str(tmp_path), "项目B", "b.md"), "w", encoding="utf-8") as f:
            f.write("B")
        with patch("app.rag.vectorstore.get_collection") as mc:
            mc.return_value.get.return_value = {"metadatas": [], "documents": [], "ids": []}
            response = client.get("/api/documents/list?project=项目A")
            data = response.json()["data"]
            docs = data["documents"]
            assert all(d["project"] == "项目A" for d in docs)

    def test_list_root_files_classified_as_未分类(self, client, tmp_path):
        """根目录文件应显示为'未分类'而不是'general'"""
        with open(os.path.join(str(tmp_path), "root.md"), "w", encoding="utf-8") as f:
            f.write("根目录文件")
        with patch("app.rag.vectorstore.get_collection") as mc:
            mc.return_value.get.return_value = {"metadatas": [], "documents": [], "ids": []}
            response = client.get("/api/documents/list")
            data = response.json()["data"]
            docs = data["documents"]
            root_doc = [d for d in docs if d["filename"] == "root.md"][0]
            assert root_doc["project"] == "未分类"


class TestUploadDocument:
    """测试文档上传 API"""

    def test_upload_rejects_unsupported_format(self, client, tmp_path):
        response = client.post(
            "/api/documents/upload",
            files={"file": ("test.exe", io.BytesIO(b"fake"), "application/octet-stream")},
        )
        assert response.status_code == 400

    def test_upload_md_file_success(self, client, tmp_path):
        with patch("app.api.documents.index_file", return_value=3) as mock_index:
            response = client.post(
                "/api/documents/upload",
                files={"file": ("test.md", io.BytesIO("# 测试".encode("utf-8")), "text/markdown")},
                params={"project": "general"}
            )
            assert response.status_code == 200
            data = response.json()["data"]
            assert data["status"] == "success"
            assert data["chunks"] == 3
            assert data["project"] == "general"

    def test_upload_creates_project_directory(self, client, tmp_path):
        with patch("app.api.documents.index_file", return_value=1):
            client.post(
                "/api/documents/upload",
                files={"file": ("test.md", io.BytesIO("# 测试".encode("utf-8")), "text/markdown")},
                params={"project": "新项目"}
            )
            assert os.path.exists(os.path.join(str(tmp_path), "新项目", "test.md"))

    def test_upload_failure_cleans_file(self, client, tmp_path):
        with patch("app.api.documents.index_file", side_effect=Exception("索引失败")):
            response = client.post(
                "/api/documents/upload",
                files={"file": ("fail.md", io.BytesIO("# 失败".encode("utf-8")), "text/markdown")},
                params={"project": "test"}
            )
            assert response.status_code == 500
            # 失败后文件应被删除
            assert not os.path.exists(os.path.join(str(tmp_path), "test", "fail.md"))


class TestDeleteDocument:
    """测试文档删除 API"""

    def test_delete_existing_file(self, client, tmp_path):
        test_file = os.path.join(str(tmp_path), "test.md")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("待删除")
        with patch("app.api.documents.chroma_delete_by_source", return_value=2), \
             patch("app.rag.bm25_store.get_bm25_store") as mock_bm25:
            mock_bm25.return_value.delete_by_source.return_value = 1
            response = client.delete("/api/documents/test.md")
            assert response.status_code == 200
            data = response.json()["data"]
            assert "filename" in data
            assert not os.path.exists(test_file)

    def test_delete_nonexistent_returns_404(self, client, tmp_path):
        response = client.delete("/api/documents/nonexistent.md")
        assert response.status_code == 404


class TestProjectStats:
    """测试项目统计 API"""

    def test_stats_returns_counts(self, client, tmp_path):
        project_dir = os.path.join(str(tmp_path), "项目A")
        os.makedirs(project_dir, exist_ok=True)
        for i in range(3):
            with open(os.path.join(project_dir, f"file{i}.md"), "w") as f:
                f.write(f"# 文档{i}")
        with patch("app.rag.vectorstore.get_collection") as mc:
            mc.return_value.get.return_value = {
                "metadatas": [{"project": "项目A"}, {"project": "项目A"}, {"project": "项目B"}],
                "documents": ["", "", ""],
                "ids": ["1", "2", "3"]
            }
            response = client.get("/api/documents/project/项目A/stats")
            assert response.status_code == 200
            data = response.json()["data"]
            assert data["file_count"] == 3
            assert data["chunk_count"] == 2  # 只有 2 个属于项目A

    def test_stats_nonexistent_project_404(self, client, tmp_path):
        response = client.get("/api/documents/project/不存在/stats")
        assert response.status_code == 404


class TestCleanupOrphaned:
    """测试孤儿索引清理 API"""

    def test_cleanup_removes_orphaned(self, client, tmp_path):
        with patch("app.rag.vectorstore.get_collection") as mc:
            mc.return_value.get.return_value = {
                "metadatas": [{"source_file": "orphan.md", "project": "test"}],
                "documents": ["孤儿内容"],
                "ids": ["id1"]
            }
            with patch("app.rag.bm25_store.get_bm25_store") as mock_bm25:
                mock_bm25.return_value.delete_by_source.return_value = 1
                response = client.post("/api/documents/cleanup")
                assert response.status_code == 200
                data = response.json()["data"]
                assert data["orphaned_files_found"] == 1
                assert "orphan.md" in data["files"]
                mc.return_value.delete.assert_called_once_with(ids=["id1"])

    def test_cleanup_no_orphans(self, client, tmp_path):
        with patch("app.rag.vectorstore.get_collection") as mc:
            mc.return_value.get.return_value = {"metadatas": [], "documents": [], "ids": []}
            response = client.post("/api/documents/cleanup")
            assert response.status_code == 200
            data = response.json()["data"]
            assert data["orphaned_files_found"] == 0
