import chromadb
import uuid
from app.config import settings
from app.rag.embeddings import get_embeddings

def get_collection(name: str = "tech_docs") -> chromadb.Collection:
    client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    return client.get_or_create_collection(name, metadata={"hnsw:space": "cosine"})

def add_documents(chunks, collection_name: str = "tech_docs"):
    collection = get_collection(collection_name)
    embeddings = get_embeddings()
    texts = [c.page_content for c in chunks]
    ids = [f"doc_{uuid.uuid4().hex[:8]}" for _ in range(len(chunks))]
    metas = [c.metadata for c in chunks]
    vectors = embeddings.embed_documents(texts)
    collection.add(documents=texts, embeddings=vectors, ids=ids, metadatas=metas)
    return len(ids)

def search_chroma(query: str, top_k: int = 5, collection_name: str = "tech_docs",
                  where: dict = None):
    """向量检索
    
    Args:
        query: 查询文本
        top_k: 返回结果数
        collection_name: 集合名
        where: Chroma 过滤条件，如 {"project": "xxx"}
    """
    collection = get_collection(collection_name)
    embeddings = get_embeddings()
    qv = embeddings.embed_query(query)
    kwargs = {"query_embeddings": [qv], "n_results": top_k}
    if where:
        kwargs["where"] = where
    return collection.query(**kwargs)

def delete_by_source(source_file: str, collection_name: str = "tech_docs"):
    """根据源文件名删除索引"""
    collection = get_collection(collection_name)
    # 获取所有文档
    all_docs = collection.get()
    if not all_docs["ids"]:
        return 0
    # 找到匹配的文档ID
    ids_to_delete = []
    for i, meta in enumerate(all_docs["metadatas"]):
        if meta.get("source_file") == source_file:
            ids_to_delete.append(all_docs["ids"][i])
    if ids_to_delete:
        collection.delete(ids=ids_to_delete)
    return len(ids_to_delete)