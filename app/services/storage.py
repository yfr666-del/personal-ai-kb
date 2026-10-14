"""存储服务：把收进来的东西落到磁盘上。

这是"收资料"阶段的第四格，也是收尾的一格。

在这格之前，上传接口是"过路不留"—— 文件读进来、解析、切分，
然后 return 出去，内存一回收就什么都没了。服务一重启，
你之前传的文档全部消失。

这一格要解决的就是：**让数据活过重启**。

存两份东西，都用 doc_id 命名：

    data/uploads/<doc_id>.<后缀>   原文件（以后要重新解析时用得上）
    data/chunks/<doc_id>.json      原文 + 切好的块（检索时直接读它）

为什么用 doc_id 而不是文件名当目录名？因为文件名会重复 ——
你传两次 `笔记.md`，后一份就把前一份覆盖了。doc_id 是系统自己发的，
不重复，也不受用户控制（用户没法用文件名搞破坏）。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# 项目根目录下的 data/（app/services/storage.py -> 往上三层）
DATA_DIR = Path(__file__).resolve().parents[2] / "data"

# doc_id 只允许这些字符。多一道保险：万一哪天 doc_id 变成用户可控的，
# 一个 "../../windows/system32" 就能把文件写到系统目录去。
_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class StorageError(Exception):
    """存储层出的问题。"""


class InvalidDocIdError(StorageError):
    """doc_id 带非法字符，拒绝操作（防路径穿越）。"""


class DocumentNotFoundError(StorageError):
    """指定的 doc_id 不存在。"""


def save_document(doc_id: str, filename: str, raw: bytes) -> Path:
    """把原文件存到磁盘，返回存到哪了。"""
    path = _upload_dir() / f"{_check_id(doc_id)}{_suffix_of(filename)}"
    path.write_bytes(raw)
    return path


def load_document(doc_id: str) -> bytes:
    """按 doc_id 把原文件读回来。"""
    _check_id(doc_id)
    for path in _upload_dir().glob(f"{doc_id}.*"):
        return path.read_bytes()
    raise DocumentNotFoundError(f"找不到文档：{doc_id}")


def save_chunks(doc_id: str, payload: dict) -> Path:
    """把「原文 + 切好的块 + 元信息」存成一个 json 文件。

    json 用 ensure_ascii=False 存 —— 否则中文会被写成 \\u4e2d 那种转义，
    文件能读但没法用眼睛看，出问题时排查很痛苦。
    """
    _check_id(doc_id)
    path = _chunk_dir() / f"{doc_id}.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return path


def load_chunks(doc_id: str) -> dict:
    """按 doc_id 把存好的那份 json 读回来。"""
    _check_id(doc_id)
    path = _chunk_dir() / f"{doc_id}.json"
    if not path.exists():
        raise DocumentNotFoundError(f"找不到文档：{doc_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def list_documents() -> list[dict]:
    """列出已存的所有文档（只读元信息，不把正文和块全拉出来）。

    以后搜索结果页、管理页面都靠这个。
    """
    docs = []
    for path in sorted(_chunk_dir().glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            # 文件坏了不该让整个列表挂掉。
            # 这里有两类"坏"：
            #   ① 内容是非法 json          -> json.JSONDecodeError
            #   ② 根本不是 utf-8 编码      -> UnicodeDecodeError
            # 而这两个都是 ValueError 的子类（UnicodeDecodeError 不是 OSError！），
            # 所以 catch ValueError 一句就能把两类一起兜住。
            continue
        docs.append(
            {
                "doc_id": data.get("doc_id", path.stem),
                "filename": data.get("filename"),
                "content_type": data.get("content_type"),
                "size_kb": data.get("size_kb"),
                "uploaded_at": data.get("uploaded_at"),
                "text_length": data.get("text_length"),
                "chunk_count": data.get("chunk_count"),
            }
        )
    return docs


def _check_id(doc_id: str) -> str:
    """确认 doc_id 是系统发的、安全的。"""
    if not _ID_PATTERN.match(doc_id or ""):
        raise InvalidDocIdError(f"非法的 doc_id：{doc_id!r}")
    return doc_id


def _suffix_of(filename: str) -> str:
    dot = filename.rfind(".")
    return filename[dot:].lower() if dot != -1 else ""


def _upload_dir() -> Path:
    d = DATA_DIR / "uploads"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _chunk_dir() -> Path:
    d = DATA_DIR / "chunks"
    d.mkdir(parents=True, exist_ok=True)
    return d
