from langchain_community.document_loaders import PyMuPDFLoader, TextLoader
from pathlib import Path
from typing import List
from langchain_core.documents import Document
from app.config import settings


def load_document(file_path: str) -> List[Document]:
    path = Path(file_path)
    ext = path.suffix.lower()
    if ext == ".pdf":
        loader = PyMuPDFLoader(file_path)
    elif ext in (".md", ".txt"):
        loader = TextLoader(file_path, encoding="utf-8")
    else:
        raise ValueError(f"不支持的文件格式: {ext}")

    docs = loader.load()
    upload_root = Path(settings.upload_dir).resolve()

    for doc in docs:
        doc.metadata["source_file"] = path.name
        # 计算相对于上传目录的路径，确定项目名
        try:
            rel = path.resolve().relative_to(upload_root)
            if len(rel.parts) == 1:
                # 根目录下的文件 → "未分类"
                doc.metadata["project"] = "未分类"
            else:
                doc.metadata["project"] = rel.parts[0]
        except ValueError:
            # 不在上传目录中
            doc.metadata["project"] = "未分类"
    return docs


def load_directory(dir_path: str) -> List[Document]:
    all_docs = []
    for f in Path(dir_path).rglob("*"):
        if f.suffix.lower() in (".pdf", ".md", ".txt"):
            all_docs.extend(load_document(str(f)))
    return all_docs
