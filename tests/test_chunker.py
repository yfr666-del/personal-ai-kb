"""切分服务（app/services/chunker.py）的规则测试。"""

import pytest

from app.models.document import ChunkConfig
from app.services.chunker import split_text


def make_paragraphs(n: int, size: int = 40) -> str:
    """造 n 个段落，每段 size 个字符，用空行隔开。"""
    return "\n\n".join(f"第{i}段" + "x" * size for i in range(n))


def make_numbered(n: int) -> str:
    """造一段带编号的文字，每个小块都长得不一样 —— 用来验证重叠。"""
    return "".join(f"<{i:04d}>" for i in range(n))


# ---------- 基本行为 ----------


def test_短文本不切_就一块():
    cfg = ChunkConfig(chunk_size=500, chunk_overlap=50)
    chunks = split_text("很短的一句话。", cfg)
    assert chunks == ["很短的一句话。"]


def test_长文本会被切成多块():
    cfg = ChunkConfig(chunk_size=100, chunk_overlap=0)
    chunks = split_text(make_paragraphs(10), cfg)
    assert len(chunks) > 1


def test_每一块都不超过chunk_size():
    cfg = ChunkConfig(chunk_size=120, chunk_overlap=20)
    chunks = split_text(make_paragraphs(12), cfg)
    assert all(len(c) <= 120 for c in chunks)


def test_没有空块():
    cfg = ChunkConfig(chunk_size=80, chunk_overlap=10)
    chunks = split_text(make_paragraphs(10), cfg)
    assert all(c.strip() for c in chunks)


# ---------- 重叠 ----------


def test_相邻块有重叠内容():
    cfg = ChunkConfig(chunk_size=200, chunk_overlap=50)
    chunks = split_text(make_numbered(200), cfg)
    assert len(chunks) >= 2
    # 上一块的尾巴，应该能在下一块里找到 —— 这就是重叠生效
    assert chunks[0][-30:] in chunks[1]


def test_重叠为零时下一块不包含上一块的尾巴():
    cfg = ChunkConfig(chunk_size=200, chunk_overlap=0)
    chunks = split_text(make_numbered(200), cfg)
    assert len(chunks) >= 2
    assert chunks[0][-30:] not in chunks[1]


# ---------- 切口质量 ----------


def test_优先在段落边界下刀_不把段落切两半():
    # 前 300 个 A，空行，再 300 个 B —— 切点应该落在空行处
    text = "A" * 300 + "\n\n" + "B" * 300
    cfg = ChunkConfig(chunk_size=500, chunk_overlap=0)
    chunks = split_text(text, cfg)
    assert chunks[0] == "A" * 300
    assert chunks[1] == "B" * 300


def test_实在没有分界线就硬切_不会卡死():
    cfg = ChunkConfig(chunk_size=100, chunk_overlap=10)
    chunks = split_text("Z" * 1000, cfg)  # 一个分界线都没有
    assert all(len(c) <= 100 for c in chunks)
    assert len(chunks) >= 10


# ---------- 覆盖性 ----------


def test_开头和结尾都不会丢():
    text = make_paragraphs(15)
    cfg = ChunkConfig(chunk_size=150, chunk_overlap=0)
    chunks = split_text(text, cfg)
    assert chunks[0].startswith("第0段")
    assert chunks[-1].endswith("x" * 40)


# ---------- 拒收 ----------


def test_空文本抛错():
    cfg = ChunkConfig()
    with pytest.raises(ValueError, match="文本为空"):
        split_text("", cfg)


def test_全空白文本抛错():
    cfg = ChunkConfig()
    with pytest.raises(ValueError, match="文本为空"):
        split_text("   \n\n  \t ", cfg)


# ---------- 和 ChunkConfig 的联动 ----------


def test_chunk_size越小块数越多():
    text = make_paragraphs(12)
    few = split_text(text, ChunkConfig(chunk_size=600, chunk_overlap=0))
    many = split_text(text, ChunkConfig(chunk_size=120, chunk_overlap=0))
    assert len(many) > len(few)


def test_默认参数下能正常切分():
    chunks = split_text(make_paragraphs(40, size=60), ChunkConfig())
    assert len(chunks) > 1
    assert all(len(c) <= 500 for c in chunks)
