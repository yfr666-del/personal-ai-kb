"""解析服务（app/services/parser.py）的规则测试。

测试里的 PDF 是现场手搓的，不往仓库里塞二进制文件 ——
这样别人 clone 下来就能跑，也不用担心夹具文件损坏。
"""

import pytest

from app.services.parser import ParseError, extract_text


def make_pdf(lines: list[str]) -> bytes:
    """手搓一份最小 PDF，返回字节。只用标准库。"""
    content = ["BT", "/F1 16 Tf", "72 720 Td"]
    for i, line in enumerate(lines):
        if i:
            content.append("0 -28 Td")
        content.append(f"({line}) Tj")
    content.append("ET")
    stream = "\n".join(content) + "\n"

    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(stream.encode('latin-1'))} >>\nstream\n{stream}endstream",
    ]

    parts = ["%PDF-1.4\n"]
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(sum(len(p.encode("latin-1")) for p in parts))
        parts.append(f"{i} 0 obj\n{body}\nendobj\n")

    xref_offset = sum(len(p.encode("latin-1")) for p in parts)
    parts.append(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n")
    for off in offsets:
        parts.append(f"{off:010d} 00000 n \n")
    parts.append(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n")
    parts.append(f"startxref\n{xref_offset}\n%%EOF\n")
    return "".join(parts).encode("latin-1")


# ---------- PDF ----------


def test_PDF能提取出文字():
    raw = make_pdf(["Hello RAG", "Second line here"])
    text = extract_text("demo.pdf", raw)
    assert "Hello RAG" in text
    assert "Second line here" in text


def test_伪装的PDF会被拒():
    # 后缀是 .pdf，内容却是随便的字节 —— 解析层要拦住
    with pytest.raises(ParseError):
        extract_text("fake.pdf", b"this is not a pdf at all")


# ---------- 纯文字 ----------


def test_md文件原样提取():
    raw = "# 标题\n\n正文内容".encode("utf-8")
    assert extract_text("note.md", raw) == "# 标题\n\n正文内容"


def test_txt文件原样提取():
    raw = "第一行\n第二行".encode("utf-8")
    assert extract_text("note.txt", raw) == "第一行\n第二行"


def test_GBK编码的中文txt也能读():
    raw = "这是GBK编码的中文".encode("gbk")
    assert extract_text("note.txt", raw) == "这是GBK编码的中文"


# ---------- 清洗规则 ----------


def test_多余空行被压缩到两个():
    raw = "A\n\n\n\n\nB".encode("utf-8")
    assert extract_text("note.md", raw) == "A\n\nB"


def test_控制字符被清掉():
    raw = "A\x00\x01B".encode("utf-8")
    assert extract_text("note.md", raw) == "AB"


def test_每行前后空白被去掉():
    raw = "   A   \n\t B \t".encode("utf-8")
    assert extract_text("note.md", raw) == "A\nB"


# ---------- 拒收 ----------


def test_不支持的后缀被拒():
    with pytest.raises(ParseError, match="暂不支持"):
        extract_text("virus.exe", b"MZ\x90\x00")


def test_没有后缀被拒():
    with pytest.raises(ParseError):
        extract_text("noext", b"hello")


def test_全空白内容被拒():
    with pytest.raises(ParseError, match="没提取到任何文字"):
        extract_text("empty.md", b"   \n\n  \t ")


def test_只有控制字符内容被拒():
    with pytest.raises(ParseError, match="没提取到任何文字"):
        extract_text("scan.md", b"\x00\x01\x02\x03")
