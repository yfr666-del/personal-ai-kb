# -*- coding: utf-8 -*-
"""检索服务：从一个问题出发，找出「哪些片段可能含着答案」。

这里同时放着**两种**检索实现，刻意让它们并列：

    keyword_search —— 数「问题里的两字片段」在片段里出现几次
    vector_search  —— 把问题和片段都换成向量，比余弦相似度

为什么要两个都留着？因为它们各有各的瞎掉方式：

    关键词：换个说法就找不到（你说"怎么跑测试"，它找不到写着 pytest 的那块）
    向量  ：能懂意思，但对精确数字、专有名词反而不稳

留着两者，同一批资料、同一个问题跑出来一对比，
各自的毛病就都暴露得清清楚楚 —— 这也是后面决定要不要加
"重排"的唯一依据：先看到排序真的持续不理想，再谈添加。
"""

from __future__ import annotations

import math

from app.models.retrieval import Candidate, CorpusChunk
from app.services import storage
from app.services.embedder import EmbeddingError, embed_texts


def load_corpus() -> list[CorpusChunk]:
    """把磁盘上所有文档的所有片段读出来，拼成一个检索库。

    片段本身只是字符串（codes 里存的是 list[str]），
    "它属于哪个文件第几块"这个信息要在这里补上，
    否则检索结果就只是一堆没有出处的句子，没法回头核对。
    """
    corpus: list[CorpusChunk] = []
    for doc in storage.list_documents():
        doc_id = doc["doc_id"]
        try:
            data = storage.load_chunks(doc_id)
        except (ValueError, OSError):
            # 单个文件坏了不该让整个库读不出来
            continue
        for i, text in enumerate(data.get("chunks", [])):
            corpus.append(
                CorpusChunk(
                    global_index=len(corpus),
                    doc_id=doc_id,
                    filename=data.get("filename") or "(未知文件名)",
                    chunk_index=i,
                    text=text,
                )
            )
    return corpus


def _to_candidates(scored: list[tuple[float, CorpusChunk]], top_k: int) -> list[Candidate]:
    """把「打分过的片段」整理成候选列表，按分数从高到低取前 top_k。

    排序时带上 global_index 做第二关键字 —— 分数相同时名次稳定，
    否则每次跑出来的顺序都不一样，没法比较。
    """
    scored.sort(key=lambda pair: (-pair[0], pair[1].global_index))
    return [
        Candidate(
            rank=i + 1,
            score=round(float(score), 4),
            chunk_index=chunk.chunk_index,
            doc_id=chunk.doc_id,
            filename=chunk.filename,
            text=chunk.text,
        )
        for i, (score, chunk) in enumerate(scored[:top_k])
    ]


def _split_words(text: str) -> list[str]:
    """把一句话切成两字一组的小片段。

    「切分是怎么做的」→ 切分 / 分是 / 是怎 / 怎么 / 么做 / 做的
    这样即使问题换了个顺序说，只要相邻两字还在，就还有机会命中。
    """
    return [text[i:i + 2] for i in range(len(text) - 1)]


def keyword_search(
    question: str, corpus: list[CorpusChunk], top_k: int = 3
) -> list[Candidate]:
    """传统关键词检索：数小片段命中了几个。

    分数字面意思是「问题里有多少个两字组合出现在这一块里」。

    注意：**0 分也会被排进来** —— 这是故意保留的真实行为，
    正好暴露"关键词检索在遇到换个说法的说法时的无能为力"。
    所以**返回了候选 ≠ 找到答案**：0 分的候选就是明证。
    """
    words = _split_words(question)
    scored = []
    for chunk in corpus:
        hit = sum(1 for w in words if w in chunk.text)
        scored.append((float(hit), chunk))
    return _to_candidates(scored, top_k)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """余弦相似度：只看两个向量的"方向"差多少，不看长度。

    本项目用的 bge-m3，在 Ollama library 的官方说明里推荐的相似度方式是余弦，
    所以这里用余弦，不用点积。

    （实测过 bge-m3 返回的向量模长为 1.0，即已归一化 ——
    在已归一化的前提下余弦与点积结果相同；这里仍显式按余弦写，
    不依赖"将来它一定还是归一化的"这个假设。）

    两个坑在这里堵住：
      1. 维度不同必须报错 —— zip 遇到长短不一会**静默截断**，
         算出一个看起来正常的分数，实际是拿一半维度算出来的。
      2. 零向量返回 0.0 —— 否则除零会炸。
    """
    if len(a) != len(b):
        raise ValueError(f"两个向量维度不一致：{len(a)} vs {len(b)}")

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def vector_search(
    question: str, corpus: list[CorpusChunk], top_k: int = 3
) -> list[Candidate]:
    """向量检索：把问题和片段都变成坐标，比夹角。

    分数是余弦相似度，范围 -1 ~ 1，越接近 1 越像。

    两条边界，别越过：

    **返回了候选 ≠ 找到答案。** 它是"按相似度排出来的一批候选"，
    至于这批里到底有没有答案，本函数不做判断 —— 资料里没有答案时，
    它照样会返回候选（实测过：问"显卡型号"，最高分 0.5155）。
    **分数高 ≠ 答案对。** 分数只说明"这两段文字意思接近"，
    跟"这段里真的有答案"是两回事。

    **当前实现每次都会重新计算全部片段的向量**，见下面代码里的注释。
    """
    if not corpus:
        return []

    # 注意：**每次查询都会把全部片段重新算一遍向量**。
    # 这是小规模演示实现（当前库里只有 10 条片段，一次不到 2 秒）；
    # 资料变大之后这里会明显变慢，缓存 / 持久化落盘不在本轮范围内，暂不引入。
    query_vec = embed_texts([question])[0]
    doc_vecs = embed_texts([c.text for c in corpus])

    # embed_texts 内部已经校验过数量，这里再断言一次：
    # 下面用 zip 把"向量"和"片段"配对，一旦两边数量不等，
    # zip 会静默截断而不是报错—— 那会变成"有几块资料永远检索不到"。
    if len(doc_vecs) != len(corpus):
        raise EmbeddingError(
            f"片段向量数量与片段数量不一致："
            f"片段 {len(corpus)} 条，向量 {len(doc_vecs)} 条"
        )

    scored = [
        (cosine_similarity(query_vec, vec), chunk)
        for vec, chunk in zip(doc_vecs, corpus)
    ]
    return _to_candidates(scored, top_k)


# ---------- 混合检索（实验性，默认不启用） ----------

RRF_K = 60


def _rrf_fuse(
    ranked_lists: list[list[CorpusChunk]], k: int = RRF_K
) -> list[tuple[float, CorpusChunk]]:
    """把若干路「已各自排好序」的片段列表，用 RRF 融成一个带分列表。

    RRF（倒数排名融合）的全部要点就是**只看名次，不看原始分数**：

        关键词路的分数 = 问题里有多少个两字组合出现在这块里（几到几十）
        向量路的分数   = 余弦相似度（-1 ~ 1）

    这两种数字没有统一单位，硬加在一起，只会让计数大的那一路永远赢。
    所以这里把每一路都降级成「名次」，再按名次给贡献。

    贡献值：`1 / (k + rank)`，rank 从 1 开始；某一路没出现就是 0。
    同一片段在**同一路**里重复出现时，只算名次最靠前的那一次。

    k 取 60 是文献里常见的起步常数，**不是针对本项目调出来的最优值**，
    也不代表它在本项目资料上有任何实测优势。

    返回 `[(融合分, 片段), ...]`，顺序未定 —— 排序交给 `_to_candidates`。
    """
    scores: dict[tuple[str, int], float] = {}
    chunks: dict[tuple[str, int], CorpusChunk] = {}

    for ranked in ranked_lists:
        seen_in_this_list: set[tuple[str, int]] = set()
        for rank, chunk in enumerate(ranked, start=1):
            key = (chunk.doc_id, chunk.chunk_index)
            if key in seen_in_this_list:
                continue
            seen_in_this_list.add(key)
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
            chunks.setdefault(key, chunk)

    return [(score, chunks[key]) for key, score in scores.items()]


def hybrid_search(
    question: str, corpus: list[CorpusChunk], top_k: int = 3
) -> list[Candidate]:
    """混合检索：关键词与向量各排一路，用 RRF 按名次融合。

    **它做了什么**：让「两路都推荐」的片段排到前面。

    **它没做什么**（这些不能靠它存在就宣称）：
      - ❌ 不表示比单路更好 —— 本轮**没有**在真实资料上跑过前后对照，没有证据
      - ❌ 关键词那路仍然不是 BM25、不是生产级引擎，只是二字组计数
      - ❌ 返回的 score 是 RRF 融合分，**不是概率，也不是答案正确率**

    三条边界：
      1. 空库直接返回 []，不会去调嵌入服务。
      2. top_k 必须是正整数 —— 不是就报错，不静默取默认值。
      3. 向量那路出错时**原样抛出**，不偷偷退化成关键词后仍显示「hybrid」。
    """
    if not corpus:
        return []

    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k <= 0:
        raise ValueError(f"top_k 必须是正整数，收到：{top_k!r}")

    # 每一路先各自看这么多（受库大小限制），融合后再截到 top_k。
    # 若直接各取 top_k，两路名单几乎不相交，融合就失去意义。
    window = min(len(corpus), max(10, top_k))

    # ---- 关键词一路 ----
    # keyword_search 的原行为保留不动：它**会**把 0 分片段也排进来
    # （那是刻意保留的真实行为，用来暴露关键词检索的无力）。
    # 但混合是例外：零命中如果也能因为"排第一"拿到 1/61，
    # 等于给完全没命中的片段发奖励 —— 所以**只在这个分支**过滤掉 0 分，
    # 并按剩余顺序重新从 1 编号（_rrf_fuse 里的 rank 来自列表位置）。
    keyword_ranked = keyword_search(question, corpus, window)
    keyword_positive = [c for c in keyword_ranked if c.score > 0]

    # ---- 向量一路 ----
    # 不捕获异常：让它原样冒出去，由调用方决定怎么告诉用户
    vector_ranked = vector_search(question, corpus, window)

    # Candidate 只是候选快照，融合要能回到库里的原片段（用 global_index 决胜并列）
    by_key = {(c.doc_id, c.chunk_index): c for c in corpus}
    keyword_chunks = [
        by_key[(c.doc_id, c.chunk_index)]
        for c in keyword_positive
        if (c.doc_id, c.chunk_index) in by_key
    ]
    vector_chunks = [
        by_key[(c.doc_id, c.chunk_index)]
        for c in vector_ranked
        if (c.doc_id, c.chunk_index) in by_key
    ]

    fused = _rrf_fuse([keyword_chunks, vector_chunks], k=RRF_K)

    # _to_candidates 会按 (-分数, global_index) 排序：
    # 并列时由 global_index 稳定决胜，分数只在展示时才舍入。
    return _to_candidates(fused, top_k)
