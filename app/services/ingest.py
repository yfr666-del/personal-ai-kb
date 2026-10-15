"""文档入库服务：让一份文件走完「校验 → 解析 → 切分 → 落盘」四关。

为什么单独抽这一层？

因为现在**有两个入口**要用同一条流水线：
    - FastAPI 的 POST /documents/upload —— 给程序调的
    - Streamlit 网页 —— 给人点的

如果两边各写一遍，哪天规则变了就得改两个地方，迟早不一致
（改了这边忘了那边，是真实项目里最常见的 bug 来源之一）。

抽到这里之后，入口层只负责「把 HTTP / 界面的杂事办好」，
业务规则全项目只有这一份。
"""

from __future__ import annotations

from uuid import uuid4

from pydantic import ValidationError

from app.models.document import ALLOWED_CONTENT_TYPES, DocumentMeta
from app.services.chunker import split_text
from app.services.parser import ParseError, extract_text
from app.services.storage import save_chunks, save_document

# 后缀 → MIME 类型。用来在浏览器没报准 MIME 时兜底
_SUFFIX_TO_CTYPE = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
}


class IngestError(Exception):
    """这份文件收不进来。message 是能直接给用户看的人话。"""


def ingest_document(
    filename: str, content_type: str | None, raw: bytes
) -> dict:
    """把一份文件的字节收进知识库，返回这趟的结果摘要。

    参数都是"原始素材"，不从磁盘读 —— 这样 HTTP 上传、网页上传、
    命令行导入都能用同一个函数。
    """
    content_type = _resolve_content_type(filename, content_type)

    # 第一关：元信息校验（后缀、类型、大小）
    # doc_id 由系统发（12 位随机十六进制），不用文件名 ——
    # 文件名会重复，你传两次「笔记.md」就会互相覆盖。
    try:
        meta = DocumentMeta(
            doc_id=uuid4().hex[:12],
            filename=filename,
            content_type=content_type,
            size_kb=max(1, len(raw) // 1024),
        )
    except ValidationError as e:
        first = e.errors()[0]
        raise IngestError(f"文件不符合要求：{first['msg']}") from e

    # 第二关：把文件内容读成文字
    try:
        text = extract_text(filename, raw)
    except ParseError as e:
        raise IngestError(f"解析失败：{e}") from e

    # 第三关：切成小块（后面给每块算"意思坐标"要用）
    # 切分参数直接取自 meta.chunk_config —— 模型里定好的规则，这里只管用
    chunks = split_text(text, meta.chunk_config)

    # 第四关：落盘。存原文件 + 一份 json（原文、块、元信息）
    # 落盘失败不包成 IngestError：那是服务端的问题（500），
    # 不是"用户文件有问题"（400），两者该分开。
    save_document(meta.doc_id, meta.filename, raw)
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

    return {
        "doc_id": meta.doc_id,
        "meta": meta,
        "size_bytes": len(raw),
        "text_length": len(text),
        "chunk_count": len(chunks),
        "first_chunk": chunks[0][:120],
    }


def _resolve_content_type(filename: str, content_type: str | None) -> str | None:
    """确定这份文件的 MIME 类型，浏览器靠不住时按后缀兜底。

    真实坑：浏览器/上传组件报的 MIME 经常不准 ——
    传 .md 文件可能报成空字符串，或者干脆报 application/octet-stream。
    这时候如果死守它，用户就会莫名其妙被拦下。
    后缀是用户自己写的、更可靠，所以拿它兜底。
    """
    if content_type in ALLOWED_CONTENT_TYPES:
        return content_type

    dot = filename.rfind(".")
    suffix = filename[dot:].lower() if dot != -1 else ""
    # 后缀也不认识就原样返回，交给模型层去报错（错误信息更清楚）
    return _SUFFIX_TO_CTYPE.get(suffix, content_type)
