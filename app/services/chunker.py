"""文本切分服务：把「一大段文字」切成「一堆小块」。

这是"收资料"阶段的第三格。为什么非切不可？

因为后面要给每一段文字算"意思坐标"（Embedding），而模型一次能吃的
文字量是有限的 —— 一份 50 页的 PDF 塞不进去。所以要切成小块，
每块单独算坐标，检索的时候按块来找。

但切分有个讲究：**不能从句子中间一刀切**。切碎了意思就残了，
检索出来的是半句话，回答质量直接崩。所以这里会尽量挑
"段落结尾 / 句号"这种天然的分界线下刀。

另外相邻两块要**故意重叠**一点 —— 万一关键信息刚好卡在切口上，
重叠区能保住它。重叠多少由 ChunkConfig 决定。
"""

from __future__ import annotations

from app.models.document import ChunkConfig

# 切分时优先找这些"天然分界线"，越靠前优先级越高
_SEPARATORS = ("\n\n", "\n", "。", "！", "？", ". ", "! ", "? ", "，", ", ")

# 允许的最短切点：太靠前的分界线会让这块短得没意义，不如直接切满
_MIN_FILL_RATIO = 0.6


def split_text(text: str, cfg: ChunkConfig) -> list[str]:
    """把 text 按 cfg 切成一堆小块，返回块的列表。

    cfg 就是模型层里那个 ChunkConfig —— chunk_size 定每块多大，
    chunk_overlap 定相邻块重叠多少。
    """
    if not text or not text.strip():
        raise ValueError("文本为空，无法切分")

    size = cfg.chunk_size
    overlap = cfg.chunk_overlap
    total = len(text)

    chunks: list[str] = []
    start = 0

    while start < total:
        end = min(start + size, total)

        # 还没到结尾，就找个好看的下刀位置
        if end < total:
            end = _find_cut(text, start, end)

        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)

        if end >= total:
            break

        # 下一块从「这一块的结尾往回退 overlap」开始 —— 这就是重叠
        start = max(end - overlap, start + 1)

    return chunks


def _find_cut(text: str, start: int, end: int) -> int:
    """在 text[start:end] 里找一个合适的下刀位置，返回绝对下标（切点之后）。

    策略：从高优先级的分界线开始找，只接受落在窗口后半段的那个；
    一个都找不到就硬切在 end。
    """
    lower = start + int((end - start) * _MIN_FILL_RATIO)

    for sep in _SEPARATORS:
        pos = text.rfind(sep, lower, end)
        if pos != -1:
            return pos + len(sep)

    return end
