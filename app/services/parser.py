"""文档解析服务：把「文件字节」变成「纯文字」。

这是"收资料"阶段的第二格 —— 上传接口负责把文件收进来，
这里负责把文件里的字掏出来。后面的切分、向量化、检索全都只认纯文字，
所以这一格是整条流水线的地基：它吐出来的东西不对，后面全白干。

对外只有一个入口：extract_text()。调用方不需要知道内部
到底用的是 pypdf 还是手写解码 —— 换实现不影响调用方。
"""

from __future__ import annotations

import io
import re

from pypdf import PdfReader


class ParseError(Exception):
    """文件收到了，但内容读不出来。

    例如：加密的 PDF、损坏的文件、纯图片扫描件（里面根本没有文字层）。
    """


# 按后缀分派：加一种新格式，只要在这里加一行 + 写一个 _extract_from_xxx
_PLAIN_SUFFIXES = (".txt", ".md")


def extract_text(filename: str, raw: bytes) -> str:
    """从文件字节里提取纯文字。

    filename 只用来判断类型（看后缀），不读磁盘。
    raw 是文件内容本身。
    """
    suffix = _suffix_of(filename)

    if suffix == ".pdf":
        text = _extract_from_pdf(raw)
    elif suffix in _PLAIN_SUFFIXES:
        text = _extract_from_plain(raw)
    else:
        raise ParseError(f"暂不支持解析 {suffix!r} 格式")

    text = _clean(text)

    # 提取不出字的常见原因：PDF 是扫描件（本质是照片），没有文字层
    if not text:
        raise ParseError("没提取到任何文字，可能是扫描件或空文件")

    return text


def _suffix_of(filename: str) -> str:
    """取小写后缀。没有后缀就返回空串。"""
    dot = filename.rfind(".")
    return filename[dot:].lower() if dot != -1 else ""


def _extract_from_plain(raw: bytes) -> str:
    """txt / md：本身就是纯文字，只要"解码"就行。

    编码不是只有 utf-8 一种。Windows 上用记事本存的中文 txt
    常常是 GBK，拿 utf-8 去解会报错或变成乱码 —— 所以先试 utf-8，
    失败就退回 gbk。这是真实项目里一定会踩的坑。
    """
    for encoding in ("utf-8", "gbk"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    # 两种都失败：硬解，把认不出的字节丢掉，至少别让接口崩掉
    return raw.decode("utf-8", errors="ignore")


def _extract_from_pdf(raw: bytes) -> str:
    """PDF：交给 pypdf 逐页把文字抠出来。

    PDF 不是"带格式的文本"，它是一套绘图指令 —— "在坐标(72,700)
    用 24 号字写下 Hello"。pypdf 干的事就是把这些绘图指令还原成文字。
    也正因为如此，纯扫描件的 PDF（只有一张图）它什么也抠不出来。
    """
    try:
        reader = PdfReader(io.BytesIO(raw))
    except Exception as e:  # pypdf 抛的异常类型很杂，统一包一层
        raise ParseError(f"PDF 打不开：{e}") from e

    if reader.is_encrypted:
        raise ParseError("PDF 已加密，无法解析")

    pages = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception as e:
            # 单页失败不拖垮整份文件，留个占位继续
            pages.append(f"[本页解析失败：{e}]")

    return "\n\n".join(pages)


def _clean(text: str) -> str:
    """清洗：统一换行、去行尾空格、压缩多余空行。

    机器抠出来的文字通常很脏：一堆连续空行、行尾空格、
    还有 PDF 里常见的 \\x00 之类的控制字符。先洗一遍，
    后面切分出来的每一块才不会是垃圾。
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # 去掉除 \n \t 以外的控制字符
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines)
    # 3 个以上连续换行 → 压成 2 个（保留段落分隔）
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
