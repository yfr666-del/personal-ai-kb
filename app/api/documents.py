"""文档相关接口。"""

from fastapi import APIRouter, HTTPException, UploadFile

from app.models.document import ALLOWED_CONTENT_TYPES, ALLOWED_SUFFIXES, DocumentMeta

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload")
async def upload_document(file: UploadFile):
    """接收上传文件，校验元信息后返回。"""
    content = await file.read()

    try:
        meta = DocumentMeta(
            doc_id=file.filename,
            filename=file.filename,
            content_type=file.content_type,
            size_kb=max(1, len(content) // 1024),
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "meta": meta,
        "size_bytes": len(content),
        "preview": content[:20].decode("utf-8", errors="ignore"),
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
