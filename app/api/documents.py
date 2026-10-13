"""文档相关接口。"""

from fastapi import APIRouter, HTTPException, UploadFile

from app.models.document import DocumentMeta

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
