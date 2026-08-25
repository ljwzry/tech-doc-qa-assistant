import os
import shutil
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from app.rag.indexer import index_file, index_directory
from app.rag.vectorstore import delete_by_source as chroma_delete_by_source
from app.rag.bm25_store import get_bm25_store
from app.utils import (
    UPLOAD_DIR, MAX_FILE_SIZE, ALLOWED_EXTENSIONS,
    success_response, error_response,
    sanitize_filename, sanitize_project_name,
    validate_file_extension, validate_file_size, get_safe_path
)

router = APIRouter(prefix="/api/documents", tags=["documents"])
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    project: Optional[str] = Query(None, description="项目名称")
):
    # 安全校验
    safe_name = sanitize_filename(file.filename)
    validate_file_extension(safe_name)
    content = await file.read()
    validate_file_size(len(content))

    # 构建安全路径
    if project:
        safe_project = sanitize_project_name(project)
        project_dir = get_safe_path(UPLOAD_DIR, safe_project)
        os.makedirs(project_dir, exist_ok=True)
        path = get_safe_path(UPLOAD_DIR, safe_project, safe_name)
    else:
        path = get_safe_path(UPLOAD_DIR, safe_name)

    with open(path, "wb") as f:
        f.write(content)

    try:
        chunks = index_file(path)
        return success_response({
            "filename": safe_name,
            "chunks": chunks,
            "status": "success",
            "project": project
        }, "上传成功")
    except Exception as e:
        if os.path.exists(path):
            os.remove(path)
        raise HTTPException(status_code=500, detail=f"索引失败: {str(e)}")


@router.post("/upload-batch")
async def upload_batch(
    files: List[UploadFile] = File(...),
    project: Optional[str] = Query(None, description="项目名称")
):
    results = []
    success_count = 0
    fail_count = 0
    total_chunks = 0

    safe_project = None
    if project:
        safe_project = sanitize_project_name(project)
        project_dir = get_safe_path(UPLOAD_DIR, safe_project)
        os.makedirs(project_dir, exist_ok=True)

    for file in files:
        try:
            safe_name = sanitize_filename(file.filename)
            validate_file_extension(safe_name)
            content = await file.read()
            validate_file_size(len(content))

            if safe_project:
                path = get_safe_path(UPLOAD_DIR, safe_project, safe_name)
            else:
                path = get_safe_path(UPLOAD_DIR, safe_name)

            with open(path, "wb") as f:
                f.write(content)

            chunks = index_file(path)
            results.append({
                "filename": safe_name, "status": "success",
                "chunks": chunks, "project": project
            })
            success_count += 1
            total_chunks += chunks
        except HTTPException as e:
            results.append({
                "filename": file.filename, "status": "failed", "error": str(e.detail)
            })
            fail_count += 1
        except Exception as e:
            if os.path.exists(path):
                os.remove(path)
            results.append({
                "filename": file.filename, "status": "failed", "error": str(e)
            })
            fail_count += 1

    return success_response({
        "total": len(files),
        "success": success_count,
        "failed": fail_count,
        "total_chunks": total_chunks,
        "details": results
    })


@router.post("/upload-directory")
async def upload_directory(
    project: str = Query(..., description="项目名称"),
    files: List[UploadFile] = File(...)
):
    if not project:
        raise HTTPException(status_code=400, detail="必须指定项目名称")

    safe_project = sanitize_project_name(project)
    project_dir = get_safe_path(UPLOAD_DIR, safe_project)
    os.makedirs(project_dir, exist_ok=True)

    results = []
    success_count = 0
    fail_count = 0
    total_chunks = 0

    for file in files:
        try:
            safe_name = sanitize_filename(file.filename)
            validate_file_extension(safe_name)
            content = await file.read()
            validate_file_size(len(content))

            # 子目录结构：从原始文件名中提取
            rel_path = file.filename.replace("\\", "/")
            if "/" in rel_path:
                sub_dir = os.path.dirname(rel_path)
                safe_sub_dir = sanitize_project_name(sub_dir)
                full_dir = get_safe_path(UPLOAD_DIR, safe_project, safe_sub_dir)
                os.makedirs(full_dir, exist_ok=True)
                path = get_safe_path(UPLOAD_DIR, safe_project, safe_sub_dir, safe_name)
            else:
                path = get_safe_path(UPLOAD_DIR, safe_project, safe_name)

            with open(path, "wb") as f:
                f.write(content)

            chunks = index_file(path)
            results.append({
                "filename": safe_name, "status": "success",
                "chunks": chunks
            })
            success_count += 1
            total_chunks += chunks
        except HTTPException as e:
            results.append({
                "filename": file.filename, "status": "failed", "error": str(e.detail)
            })
            fail_count += 1
        except Exception as e:
            if os.path.exists(path):
                os.remove(path)
            results.append({
                "filename": file.filename, "status": "failed", "error": str(e)
            })
            fail_count += 1

    return success_response({
        "project": project,
        "total": len(files),
        "success": success_count,
        "failed": fail_count,
        "total_chunks": total_chunks,
        "details": results
    })


@router.get("/list")
async def list_documents(project: Optional[str] = Query(None, description="项目名称")):
    docs = []
    orphaned = []

    # 统一解析上传目录的绝对路径
    upload_dir_resolved = Path(UPLOAD_DIR).resolve()

    if os.path.exists(UPLOAD_DIR):
        from app.rag.vectorstore import get_collection
        collection = get_collection()
        all_indexed = collection.get()
        indexed_sources = set()
        if all_indexed and all_indexed.get("metadatas"):
            for meta in all_indexed["metadatas"]:
                src = meta.get("source_file", "")
                if src:
                    indexed_sources.add(src)

        disk_sources = set()

        if project:
            safe_project = sanitize_project_name(project)
            project_dir = get_safe_path(UPLOAD_DIR, safe_project)
            project_dir_resolved = Path(project_dir).resolve()
            if os.path.exists(project_dir):
                for f in project_dir_resolved.rglob("*"):
                    if f.is_file() and f.suffix.lower() in ALLOWED_EXTENSIONS:
                        disk_sources.add(f.name)
                        rel_path = str(f.relative_to(project_dir_resolved))
                        is_indexed = f.name in indexed_sources
                        docs.append({
                            "filename": f.name, "project": project,
                            "path": rel_path, "indexed": is_indexed
                        })
        else:
            for f in upload_dir_resolved.rglob("*"):
                if f.is_file() and f.suffix.lower() in ALLOWED_EXTENSIONS:
                    disk_sources.add(f.name)
                    try:
                        rel = f.relative_to(upload_dir_resolved)
                        if len(rel.parts) == 1:
                            project_name = "未分类"
                        else:
                            project_name = rel.parts[0]
                        rel_path = str(rel)
                    except ValueError:
                        project_name = f.parent.name
                        rel_path = str(f.name)
                    is_indexed = f.name in indexed_sources
                    docs.append({
                        "filename": f.name, "project": project_name,
                        "path": rel_path, "indexed": is_indexed
                    })

        orphaned_sources = indexed_sources - disk_sources
        for src in sorted(orphaned_sources):
            chunk_count = sum(
                1 for meta in (all_indexed.get("metadatas", []) or [])
                if meta.get("source_file") == src
            )
            orphaned.append({"filename": src, "chunks": chunk_count})

    return success_response({"documents": docs, "orphaned": orphaned})


@router.get("/projects")
async def list_projects():
    projects = []
    if os.path.exists(UPLOAD_DIR):
        for item in os.listdir(UPLOAD_DIR):
            item_path = os.path.join(UPLOAD_DIR, item)
            if os.path.isdir(item_path) and not item.startswith("."):
                projects.append(item)
    if "general" not in projects:
        projects.insert(0, "general")
    return success_response({"projects": projects})


@router.get("/project/{project}/stats")
async def project_stats(project: str):
    safe_project = sanitize_project_name(project)
    project_dir = get_safe_path(UPLOAD_DIR, safe_project)

    if not os.path.exists(project_dir):
        raise HTTPException(status_code=404, detail="项目不存在")

    file_count = 0
    for f in Path(project_dir).rglob("*"):
        if f.suffix.lower() in ALLOWED_EXTENSIONS:
            file_count += 1

    from app.rag.vectorstore import get_collection
    collection = get_collection()
    all_docs = collection.get()
    chunk_count = sum(
        1 for meta in all_docs.get("metadatas", [])
        if meta.get("project") == safe_project
    )

    return success_response({
        "project": safe_project,
        "file_count": file_count,
        "chunk_count": chunk_count
    })


@router.post("/reindex")
async def reindex_unindexed(project: Optional[str] = Query(None, description="项目名称，不传则扫描全部")):
    from app.rag.indexer import index_file
    from app.rag.vectorstore import get_collection

    collection = get_collection()
    all_indexed = collection.get()
    indexed_sources = set()
    if all_indexed and all_indexed.get("metadatas"):
        for meta in all_indexed["metadatas"]:
            src = meta.get("source_file", "")
            if src:
                indexed_sources.add(src)

    results = []
    success_count = 0
    fail_count = 0
    total_chunks = 0

    if project:
        safe_project = sanitize_project_name(project)
        scan_dirs = [get_safe_path(UPLOAD_DIR, safe_project)]
    else:
        scan_dirs = [UPLOAD_DIR]

    for scan_dir in scan_dirs:
        if not os.path.exists(scan_dir):
            continue
        for f in Path(scan_dir).rglob("*"):
            if f.suffix.lower() in ALLOWED_EXTENSIONS:
                if f.name not in indexed_sources:
                    try:
                        chunks = index_file(str(f))
                        success_count += 1
                        total_chunks += chunks
                        results.append({"file": f.name, "status": "success", "chunks": chunks})
                    except Exception as e:
                        fail_count += 1
                        results.append({"file": f.name, "status": "failed", "error": str(e)})

    return success_response({
        "total": success_count + fail_count,
        "success": success_count,
        "failed": fail_count,
        "total_chunks": total_chunks,
        "details": results
    })


@router.post("/cleanup")
async def cleanup_orphaned():
    from app.rag.vectorstore import get_collection
    from app.rag.bm25_store import get_bm25_store

    collection = get_collection()
    all_docs = collection.get()

    disk_sources = set()
    if os.path.exists(UPLOAD_DIR):
        for f in Path(UPLOAD_DIR).rglob("*"):
            if f.suffix.lower() in ALLOWED_EXTENSIONS:
                disk_sources.add(f.name)

    chroma_orphaned = set()
    if all_docs and all_docs.get("metadatas"):
        for meta in all_docs["metadatas"]:
            src = meta.get("source_file", "")
            if src and src not in disk_sources:
                chroma_orphaned.add(src)

    chroma_deleted_total = 0
    if chroma_orphaned and all_docs:
        ids_to_delete = []
        for i, meta in enumerate(all_docs["metadatas"]):
            if meta.get("source_file", "") in chroma_orphaned:
                ids_to_delete.append(all_docs["ids"][i])
                chroma_deleted_total += 1
        if ids_to_delete:
            collection.delete(ids=ids_to_delete)

    bm25 = get_bm25_store()
    bm25_deleted_total = 0
    for src in chroma_orphaned:
        bm25_deleted = bm25.delete_by_source(src)
        bm25_deleted_total += bm25_deleted

    return success_response({
        "orphaned_files_found": len(chroma_orphaned),
        "chroma_chunks_deleted": chroma_deleted_total,
        "bm25_chunks_deleted": bm25_deleted_total,
        "files": sorted(chroma_orphaned)
    })


@router.delete("/{filename}")
async def delete_document(
    filename: str,
    project: Optional[str] = Query(None, description="项目名称")
):
    safe_name = sanitize_filename(filename)

    if project:
        safe_project = sanitize_project_name(project)
        path = get_safe_path(UPLOAD_DIR, safe_project, safe_name)
    else:
        path = get_safe_path(UPLOAD_DIR, safe_name)

    if os.path.exists(path):
        os.remove(path)
        chroma_deleted = chroma_delete_by_source(safe_name)
        bm25_deleted = get_bm25_store().delete_by_source(safe_name)
        return success_response({
            "filename": safe_name,
            "chroma_deleted": chroma_deleted,
            "bm25_deleted": bm25_deleted
        }, "删除成功")
    raise HTTPException(status_code=404, detail="文件不存在")


@router.delete("/project/{project}")
async def delete_project(project: str):
    safe_project = sanitize_project_name(project)
    project_dir = get_safe_path(UPLOAD_DIR, safe_project)

    if not os.path.exists(project_dir):
        raise HTTPException(status_code=404, detail="项目不存在")

    # 使用 shutil.rmtree 删除整个项目目录（包括子目录）
    shutil.rmtree(project_dir)

    # 清理该项目的索引
    from app.rag.vectorstore import get_collection
    collection = get_collection()
    all_docs = collection.get()
    ids_to_delete = []
    for i, meta in enumerate(all_docs.get("metadatas", [])):
        if meta.get("project") == safe_project:
            ids_to_delete.append(all_docs["ids"][i])
    if ids_to_delete:
        collection.delete(ids=ids_to_delete)

    bm25_store = get_bm25_store()
    bm25_deleted = bm25_store.delete_by_project(safe_project)

    return success_response({
        "project": safe_project,
        "chroma_deleted": len(ids_to_delete),
        "bm25_deleted": bm25_deleted
    }, "项目删除成功")
