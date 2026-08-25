from app.rag.loader import load_document, load_directory
from app.rag.splitter import split_documents
from app.rag.vectorstore import add_documents
from app.rag.bm25_store import get_bm25_store

def index_file(file_path: str) -> int:
    docs = load_document(file_path)
    chunks = split_documents(docs)
    add_documents(chunks)
    get_bm25_store().add_documents([{"text": c.page_content, "metadata": c.metadata} for c in chunks])
    return len(chunks)

def index_directory(dir_path: str) -> int:
    docs = load_directory(dir_path)
    chunks = split_documents(docs)
    add_documents(chunks)
    get_bm25_store().add_documents([{"text": c.page_content, "metadata": c.metadata} for c in chunks])
    return len(chunks)