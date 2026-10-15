"""文档相关接口。

这一层只干两件事：把 HTTP 的东西翻译成业务调用，把结果/错误翻译回 HTTP。
真正的业务（校验、解析、切分、落盘）全在 app/services/ingest.py。
"""

from fastapi import APIRouter, HTTPException, UploadFile

from app.models.document import ALLOWED_CONTENT_TYPES, ALLOWED_SUFFIXES
from app.services.ingest import IngestError, ingest_document
from app.services.storage import (
    DocumentNotFoundError,
    StorageError,
    list_documents,
    load_chunks,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload")
async def upload_document(file: UploadFile):
    """接收上传文件：校验 -> 解析 -> 切分 -> 落盘。

    这里读到的 file.filename / content_type 是浏览器报的，
    不一定准 —— 具体怎么处理，在 ingest_document 里。
    """
    content = await file.read()

    try:
        return ingest_document(file.filename, file.content_type, content)
    except IngestError as e:
        # 400：用户的问题（格式不对、内容读不出来）
        raise HTTPException(status_code=400, detail=str(e))
    except StorageError as e:
        # 500：服务端的问题（磁盘写不进去）
        raise HTTPException(status_code=500, detail=f"落盘失败：{e}")


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
