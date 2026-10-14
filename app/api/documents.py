"""文档相关接口。"""

from uuid import uuid4

from fastapi import APIRouter, HTTPException, UploadFile

from app.models.document import ALLOWED_CONTENT_TYPES, ALLOWED_SUFFIXES, DocumentMeta
from app.services.chunker import split_text
from app.services.parser import ParseError, extract_text
from app.services.storage import (
    DocumentNotFoundError,
    StorageError,
    list_documents,
    load_chunks,
    save_chunks,
    save_document,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload")
async def upload_document(file: UploadFile):
    """接收上传文件：校验 -> 解析 -> 切分 -> 落盘。

    四关走完，这份文档才算真正"收进来"了。
    """
    content = await file.read()

    # 第一关：元信息校验（后缀、类型、大小）
    # doc_id 由系统发（12 位随机十六进制），不用文件名 ——
    # 文件名会重复，你传两次「笔记.md」就会互相覆盖。
    try:
        meta = DocumentMeta(
            doc_id=uuid4().hex[:12],
            filename=file.filename,
            content_type=file.content_type,
            size_kb=max(1, len(content) // 1024),
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 第二关：把文件内容读成文字
    try:
        text = extract_text(file.filename, content)
    except ParseError as e:
        raise HTTPException(status_code=400, detail=f"解析失败：{e}")

    # 第三关：切成小块（后面给每块算"意思坐标"要用）
    # 切分参数直接取自 meta.chunk_config —— 模型里定好的规则，这里只管用
    chunks = split_text(text, meta.chunk_config)

    # 第四关：落盘。存原文件 + 一份 json（原文、块、元信息）
    try:
        save_document(meta.doc_id, meta.filename, content)
        save_chunks(
            meta.doc_id,
            {
                "doc_id": meta.doc_id,
                "filename": meta.filename,
                "content_type": meta.content_type,
                "size_kb": meta.size_kb,
                "uploaded_at": meta.uploaded_at.isoformat(),
                "chunk_config": meta.chunk_config.model_dump(),
                "text_length": len(text),
                "chunk_count": len(chunks),
                "text": text,
                "chunks": chunks,
            },
        )
    except StorageError as e:
        raise HTTPException(status_code=500, detail=f"落盘失败：{e}")

    return {
        "doc_id": meta.doc_id,
        "meta": meta,
        "size_bytes": len(content),
        "text_length": len(text),
        "chunk_count": len(chunks),
        "first_chunk": chunks[0][:120],
    }


@router.get("/allowed")
async def list_allowed_types():
    """返回系统允许上传的文件类型。

    这里不重新写一遍 .pdf/.txt/.md，而是直接读模型层的常量 ——
    规则只有一处，改白名单时不用满项目找。
    """
    return {
        "allowed_extensions": list(ALLOWED_SUFFIXES),
        "allowed_content_types": list(ALLOWED_CONTENT_TYPES),
    }


@router.get("")
async def list_all_documents():
    """列出已收进来的所有文档。

    注意它注册在 /{doc_id} 前面 —— FastAPI 是按注册顺序匹配的，
    要是反了，访问 /documents/allowed 会被当成 doc_id="allowed"。
    """
    docs = list_documents()
    return {"count": len(docs), "documents": docs}


@router.get("/{doc_id}")
async def get_document(doc_id: str):
    """按 doc_id 取一份文档的完整内容（含所有切好的块）。"""
    try:
        data = load_chunks(doc_id)
    except DocumentNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "doc_id": data["doc_id"],
        "filename": data["filename"],
        "chunk_count": data["chunk_count"],
        "text_length": data["text_length"],
        "chunks": data["chunks"],
    }
