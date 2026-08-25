from langchain_text_splitters import RecursiveCharacterTextSplitter, MarkdownHeaderTextSplitter
from langchain_core.documents import Document
from typing import List

def split_documents(docs: List[Document]) -> List[Document]:
    all_chunks = []
    for doc in docs:
        ext = doc.metadata.get("source_file", "").split(".")[-1].lower()
        if ext == "md":
            all_chunks.extend(_split_markdown(doc))
        else:
            all_chunks.extend(_split_generic(doc))
    return all_chunks

def _split_markdown(doc: Document) -> List[Document]:
    headers = [("#", "h1"), ("##", "h2"), ("###", "h3")]
    splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers)
    chunks = splitter.split_text(doc.page_content)
    fallback = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50,
        separators=["\n\n", "\n", "。", ",", " ", ""])
    final = []
    for c in chunks:
        if len(c.page_content) > 600:
            final.extend(fallback.split_documents([c]))
        else:
            final.append(c)
    for c in final:
        c.metadata.update(doc.metadata)
    return final

def _split_generic(doc: Document) -> List[Document]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50,
        separators=["\n\n", "\n", "。", ",", " ", ""])
    return splitter.split_documents([doc])