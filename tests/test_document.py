"""DocumentMeta 的规则测试。

一个测试函数 = 一条规则。名字写成一句话，跑起来就是一份规则清单。
跑法（在项目根目录）：
    .venv\\Scripts\\python.exe -m pytest -v
"""

import pytest
from pydantic import ValidationError

from app.models.document import ChunkConfig, DocumentMeta


def make_meta(**overrides):
    """造一份合法的基础数据；要改哪个字段就传哪个。

    这样每个测试只表达「我改了什么、期望什么」，不用重复抄一堆字段。
    """
    data = {
        "doc_id": "d1",
        "filename": "note.md",
        "content_type": "text/markdown",
        "size_kb": 10,
    }
    data.update(overrides)
    return DocumentMeta(**data)


def test_合法数据能通过():
    meta = make_meta()
    assert meta.filename == "note.md"
    assert meta.size_kb == 10


def test_默认值生效_标签为空列表_来源为空():
    meta = make_meta()
    assert meta.tags == []
    assert meta.source_url is None
    assert meta.uploaded_at is not None


def test_两个实例的标签互不影响():
    """default_factory 的意义：每次新建一个空列表，而不是共用同一个。

    如果当初写成 tags: list[str] = []，这里就会挂 —— 一个是空列表，
    另一个也会被连带改掉（Python 默认参数的老坑）。
    """
    a = make_meta()
    b = make_meta()
    a.tags.append("x")
    assert b.tags == []


def test_文件名带斜杠被拒():
    with pytest.raises(ValidationError):
        make_meta(filename="dir/note.md")


def test_文件名带反斜杠被拒():
    with pytest.raises(ValidationError):
        make_meta(filename="dir\\note.md")


def test_文件名后缀不在白名单被拒():
    with pytest.raises(ValidationError):
        make_meta(filename="evil.png")


def test_content_type不在白名单被拒():
    with pytest.raises(ValidationError):
        make_meta(content_type="image/png")


def test_大小为0被拒():
    with pytest.raises(ValidationError):
        make_meta(size_kb=0)


def test_大小超上限被拒():
    with pytest.raises(ValidationError):
        make_meta(size_kb=51201)


def test_标签会去空白去空串并去重():
    meta = make_meta(tags=[" ai ", "ai", "", "   ", "rag"])
    assert meta.tags == ["ai", "rag"]


def test_切分重叠必须小于块大小():
    with pytest.raises(ValidationError):
        ChunkConfig(chunk_size=100, chunk_overlap=100)


def test_切分参数合法时能通过():
    cfg = ChunkConfig(chunk_size=500, chunk_overlap=50)
    assert cfg.chunk_size == 500
    assert cfg.chunk_overlap == 50
