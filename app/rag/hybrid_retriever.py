import hashlib
import os
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor
from app.rag.vectorstore import search_chroma, get_collection
from app.rag.bm25_store import get_bm25_store
from app.config import settings

# 复用线程池，避免每次检索都创建新线程
_executor = ThreadPoolExecutor(max_workers=2)

def _doc_key(text: str, source_file: str) -> str:
    """生成文档的唯一标识 key"""
    return f"{source_file}_{hashlib.md5(text.encode('utf-8')).hexdigest()}"

def _get_project_names() -> List[str]:
    """动态扫描 upload_dir 目录获取所有项目名称，按名称长度降序（避免子串误匹配）"""
    docs_dir = os.path.abspath(settings.upload_dir)
    if os.path.isdir(docs_dir):
        names = [d for d in os.listdir(docs_dir)
                 if os.path.isdir(os.path.join(docs_dir, d)) and not d.startswith(".")]
        # 长名优先匹配，避免 'general' 误匹配 'general-knowledge'
        return sorted(names, key=len, reverse=True)
    return []

def get_document_chunks(source_file: str, project: str = None, max_chunks: int = 10) -> List[Dict[str, Any]]:
    """获取指定文档的 chunk
    
    Args:
        source_file: 源文件名
        project: 项目名称
        max_chunks: 最大返回chunk数量，避免返回过多内容导致卡顿
    """
    collection = get_collection()
    if project:
        where_filter = {"$and": [{"source_file": source_file}, {"project": project}]}
    else:
        where_filter = {"source_file": source_file}
    
    results = collection.get(where=where_filter)
    if results and results["documents"]:
        chunks = []
        for i, doc in enumerate(results["documents"]):
            if i >= max_chunks:
                break
            metadata = results["metadatas"][i] if results["metadatas"] else {}
            chunks.append({"text": doc, "metadata": metadata})
        return chunks
    
    return []

def hybrid_search(query: str, top_k: int = 5, alpha: float = 0.3, 
                  project: str = None) -> List[Dict[str, Any]]:
    """混合检索：向量 + BM25，alpha 为向量权重
    
    Args:
        query: 搜索查询
        top_k: 返回结果数量
        alpha: 向量检索权重 (0-1)，降低此值可提高关键词匹配的权重
        project: 项目名称，可选，指定后只检索该项目的文档
    """
    import re
    
    # 从查询中提取项目名称（当没有指定project参数时）
    # 动态扫描 data/docs 目录，新增项目无需改代码即可识别
    detected_project = project
    if not detected_project:
        project_names = _get_project_names()
        
        # Step 1: 先检查查询中是否包含具体项目名称（最精确的匹配）
        # 例如 "项目A怎么部署" → 命中 "项目A"
        for proj_name in project_names:
            if proj_name in query:
                detected_project = proj_name
                break
    
    # Step 2: 若仍未识别，检查是否为关于本系统（TechDoc QA Assistant = general）的问题
    # 只有"自身指代"类关键词才强制锁定 general，操作类关键词需结合上下文
    if not detected_project:
        # "技术文档问答助手" / "本系统" / "这个助手" → 用户明确在问"你"自己
        self_project_keywords = [
            "技术文档问答助手", "技术文档智能问答", "techdoc qa", "tech-doc-qa",
            "本助手", "这个助手", "你的", "你自己", "这个问答助手",
        ]
        # "本项目" / "本平台" → 可能指当前选中的项目，也可能指自身
        # 仅当用户明确用第一人称指代"你"时才锁定 general
        query_lower = query.lower()
        matched_self = any(kw.lower() in query_lower for kw in self_project_keywords)
        if matched_self and "general" in project_names:
            detected_project = "general"
    
    # Step 3: 若仍未识别，且查询中没有任何项目线索，
    # 检查操作类关键词是否明显在问"本系统"的使用方法
    # （仅限"怎么用"/"使用说明"/"操作指南"这类明确指向自身使用的问题）
    if not detected_project:
        self_usage_keywords = [
            "怎么用", "如何使用", "使用说明", "操作指南", "操作手册",
            "使用指南", "怎么使用", "如何用", "怎么操作",
        ]
        # 排除"部署"/"启动"/"安装"等可能属于任意项目的操作
        # 只有"使用说明"/"操作指南"这类明显是在问系统自身用法的关键词才锁定 general
        if any(kw.lower() in query.lower() for kw in self_usage_keywords):
            if "general" in project_names:
                detected_project = "general"
    
    # 优先检测文件名匹配 - 如果查询中包含文件名，直接返回该文档的所有内容
    # 匹配带后缀的文件名（如 README.md），排除空格和特殊字符
    filename_match = re.search(r'([\w\-\.]+?\.(md|pdf|txt))', query, re.IGNORECASE)
    if filename_match:
        source_file = filename_match.group(1)
        doc_chunks = get_document_chunks(source_file, detected_project)
        if doc_chunks:
            return doc_chunks
    
    # 匹配常见的文档名称模式（如 README, api-design, architecture 等）
    # 使用简单的包含匹配，因为正则边界匹配在中文语境下有问题
    common_doc_patterns = [
        ('readme', ['README.md', 'readme.md', 'Readme.md']),
        ('api', ['api-design.md', 'API-design.md']),
        ('architecture', ['architecture.md', 'Architecture.md']),
        ('database', ['database-design.md', 'Database-design.md']),
        ('deploy', ['deploy-guide.md', 'Deploy-guide.md']),
        ('payment', ['payment-system.md', 'Payment-system.md']),
        ('video', ['video-transcode.md', 'Video-transcode.md']),
        ('部署使用说明', ['部署使用说明.md']),
        ('项目架构接口说明', ['项目架构接口说明.md']),
        ('冬枣种植', ['冬枣种植智慧大棚物联网平台-后端部署与项目说明文档.md']),
        ('nanobot', ['nanobot项目文档及复用说明.md']),
        ('redis', ['redis-cache-strategy.md']),
        ('tdengine', ['tdengine-guide.md']),
        ('数据库设计', ['database-design.md']),
        ('系统架构', ['architecture.md']),
        ('部署指南', ['deploy-guide.md']),
        ('支付系统', ['payment-system.md']),
        ('视频转码', ['video-transcode.md']),
        # general 目录下的本项目文档
        ('部署操作手册', ['部署操作手册.md']),
        ('部署手册', ['部署操作手册.md']),
        ('部署操作', ['部署操作手册.md']),
        ('操作手册', ['部署操作手册.md']),
        ('AI模型配置', ['AI模型配置指南.md']),
        ('模型配置', ['AI模型配置指南.md']),
        ('配置指南', ['AI模型配置指南.md']),
        ('API接口', ['api-design.md']),
    ]
    for pattern, filenames in common_doc_patterns:
        if pattern.lower() in query.lower():
            for filename in filenames:
                doc_chunks = get_document_chunks(filename, detected_project)
                if doc_chunks:
                    return doc_chunks
    
    # 向量检索 + BM25 检索并行执行（两者无依赖关系）
    where_filter = {"project": detected_project} if detected_project else None
    future_v = _executor.submit(search_chroma, query, top_k * 2, "tech_docs", where_filter)
    future_b = _executor.submit(get_bm25_store().search, query, top_k * 2)
    vr = future_v.result()
    bm25_results = future_b.result()

    v_docs = []
    if vr and vr["documents"]:
        for i, doc in enumerate(vr["documents"][0]):
            metadata = vr["metadatas"][0][i] if vr["metadatas"] else {}
            v_docs.append({"text": doc,
                "metadata": metadata,
                "vector_score": 1.0 / (i + 1), "bm25_score": 0.0})
    # BM25 检索后过滤（BM25 不支持 where 条件）
    if detected_project:
        bm25_results = [r for r in bm25_results if r["metadata"].get("project") == detected_project]
    # RRF 融合
    fused = {}
    for d in v_docs:
        key = _doc_key(d["text"], d["metadata"].get("source_file", ""))
        fused[key] = d
    for rank, d in enumerate(bm25_results):
        key = _doc_key(d["text"], d["metadata"].get("source_file", ""))
        if key in fused:
            fused[key]["bm25_score"] = 1.0 / (rank + 1)
        else:
            fused[key] = {"text": d["text"], "metadata": d["metadata"], "vector_score": 0.0, "bm25_score": 1.0 / (rank + 1)}
    results = []
    for data in fused.values():
        score = alpha * data["vector_score"] + (1 - alpha) * data["bm25_score"]
        results.append({"text": data["text"], "metadata": data["metadata"], "score": score})
    results.sort(key=lambda x: x["score"], reverse=True)
    
    return results[:top_k]