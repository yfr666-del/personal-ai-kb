"""存储服务（app/services/storage.py）的规则测试。

关键点：每个测试都用 tmp_path 当 data 目录，
绝不能往项目真实的 data/ 里写测试垃圾。
"""

import asyncio
import io
import json

import pytest
from starlette.datastructures import Headers, UploadFile

from app.api.documents import upload_document
from app.services import storage
from app.services.storage import (
    DocumentNotFoundError,
    InvalidDocIdError,
    list_documents,
    load_chunks,
    load_document,
    save_chunks,
    save_document,
)


@pytest.fixture(autouse=True)
def 隔离的data目录(tmp_path, monkeypatch):
    """每个测试都换一个全新的空 data 目录。"""
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    return tmp_path


# ---------- 原文件 ----------


def test_存进去能原样读回来():
    raw = "# hello\n正文内容".encode("utf-8")
    save_document("abc123", "note.md", raw)
    assert load_document("abc123") == raw


def test_后缀会被保留():
    save_document("abc123", "note.md", b"x")
    found = list((storage.DATA_DIR / "uploads").glob("*"))
    assert [p.name for p in found] == ["abc123.md"]


def test_读不存在的文档会抛错():
    with pytest.raises(DocumentNotFoundError):
        load_document("nope")


# ---------- 块数据 ----------


def test_块数据往返一致():
    payload = {"doc_id": "abc123", "filename": "a.md", "chunks": ["块一", "块二"]}
    save_chunks("abc123", payload)
    assert load_chunks("abc123") == payload


def test_中文不会被转义成unicode():
    save_chunks("abc123", {"filename": "我的笔记.md", "chunks": ["中文块"]})
    raw = (storage.DATA_DIR / "chunks" / "abc123.json").read_text(encoding="utf-8")
    assert "我的笔记.md" in raw
    assert "\\u" not in raw


def test_读不存在的块数据会抛错():
    with pytest.raises(DocumentNotFoundError):
        load_chunks("nope")


# ---------- 列表 ----------


def test_列表初始为空():
    assert list_documents() == []


def test_列表包含已存的文档():
    save_chunks("aaa111", {"doc_id": "aaa111", "filename": "a.md", "chunk_count": 3})
    save_chunks("bbb222", {"doc_id": "bbb222", "filename": "b.md", "chunk_count": 5})
    docs = list_documents()
    assert len(docs) == 2
    assert {d["doc_id"] for d in docs} == {"aaa111", "bbb222"}


def test_列表不会因为一个坏文件崩掉():
    save_chunks("aaa111", {"doc_id": "aaa111", "filename": "a.md"})
    # 注意 encoding="utf-8" 不能省！
    # 省掉的话会用「系统默认编码」（Windows 中文系统 = GBK），
    # 写出来的字节不是合法 utf-8，测试结果就会随机器而变。
    (storage.DATA_DIR / "chunks" / "broken.json").write_text(
        "{ 这不是合法json", encoding="utf-8"
    )
    docs = list_documents()
    assert [d["doc_id"] for d in docs] == ["aaa111"]


def test_列表能容忍不是utf8编码的文件():
    """回归测试：文件是 GBK 编码时，列表也必须活着。

    这条是有血的教训的 —— 之前只 catch 了 json.JSONDecodeError，
    遇到 UnicodeDecodeError 直接整个列表崩掉。
    """
    save_chunks("aaa111", {"doc_id": "aaa111", "filename": "a.md"})
    (storage.DATA_DIR / "chunks" / "gbk.json").write_bytes(
        "{ 这是一个GBK编码的文件".encode("gbk")
    )
    docs = list_documents()
    assert [d["doc_id"] for d in docs] == ["aaa111"]


# ---------- 安全：防路径穿越 ----------


@pytest.mark.parametrize(
    "坏id",
    ["../../windows/system32", "a/b", "a\\b", "", "带中文的id", "a" * 100],
)
def test_非法doc_id一律拒绝(坏id):
    with pytest.raises(InvalidDocIdError):
        save_document(坏id, "note.md", b"x")
    with pytest.raises(InvalidDocIdError):
        save_chunks(坏id, {"doc_id": 坏id})
    with pytest.raises(InvalidDocIdError):
        load_chunks(坏id)


def test_合法doc_id可以通过():
    save_document("Abc-123_x", "note.md", b"x")  # 不该抛异常


# ---------- 和接口层的联动（端到端） ----------


def 上传(name: str, data: bytes, ctype: str) -> dict:
    f = UploadFile(
        filename=name, file=io.BytesIO(data), headers=Headers({"content-type": ctype})
    )
    return asyncio.run(upload_document(f))


def test_上传后文件真的落到磁盘上了():
    result = 上传("note.md", "第一段。\n\n第二段。".encode("utf-8"), "text/markdown")
    doc_id = result["doc_id"]

    # 原文件在
    assert (storage.DATA_DIR / "uploads" / f"{doc_id}.md").exists()
    # json 在，且内容对得上
    stored = json.loads(
        (storage.DATA_DIR / "chunks" / f"{doc_id}.json").read_text(encoding="utf-8")
    )
    assert stored["filename"] == "note.md"
    assert stored["chunk_count"] == result["chunk_count"]
    assert "第一段。" in stored["text"]


def test_传两次同名文件不会互相覆盖():
    a = 上传("笔记.md", b"AAAA", "text/markdown")
    b = 上传("笔记.md", b"BBBB", "text/markdown")
    assert a["doc_id"] != b["doc_id"]
    assert load_document(a["doc_id"]) == b"AAAA"
    assert load_document(b["doc_id"]) == b"BBBB"
    assert len(list_documents()) == 2


def test_上传失败的文件不会留下垃圾():
    with pytest.raises(Exception):
        # .png 第一关就被拦下，不该有任何文件落盘
        上传("evil.png", b"\x89PNG", "image/png")
    assert list_documents() == []
    assert list((storage.DATA_DIR / "uploads").glob("*")) == []
