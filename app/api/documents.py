"""文档相关接口。"""

from fastapi import APIRouter, HTTPException, UploadFile

from app.models.document import ALLOWED_CONTENT_TYPES, ALLOWED_SUFFIXES, DocumentMeta
from app.services.chunker import split_text
from app.services.parser import ParseError, extract_text

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload")
async def upload_document(file: UploadFile):
    """接收上传文件，校验元信息，并把文件里的文字解析出来。"""
    content = await file.read()

    # 第一关：元信息校验（后缀、类型、大小）
    try:
        meta = DocumentMeta(
            doc_id=file.filename,
            filename=file.filename,
            content_type=file.content_type,
            size_kb=max(1, len(content) // 1024),
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 第二关：真正把文件内容读成文字
    try:
        text = extract_text(file.filename, content)
    except ParseError as e:
        raise HTTPException(status_code=400, detail=f"解析失败：{e}")

    # 第三关：切成小块（后面给每块算"意思坐标"要用）
    # 切分参数直接取自 meta.chunk_config —— 模型里定好的规则，这里只管用
    chunks = split_text(text, meta.chunk_config)

    return {
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
