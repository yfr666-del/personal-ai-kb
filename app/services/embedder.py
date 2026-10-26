# -*- coding: utf-8 -*-
"""本地嵌入服务：把「一段文字」变成「一串数字」（向量）。

这一层只做一件事：向本地 Ollama 的 /api/embed 发请求，把向量拿回来。

**为什么要跟聊天调用分开写？**

因为「聊天」和「嵌入」是两种完全不同的能力：

    聊天模型（本项目 qwen3:4b）  吃一段话 → 吐一段话
    嵌入模型（本项目 bge-m3）    吃一段话 → 吐一串数字（这段话的"意思坐标"）

混在一个函数里，迟早会写出「顺手用聊天模型算个向量」这种东西 ——
那算出来的数字没有意义，但不会报错，是最难发现的一类 bug。
所以这里单独一个模块，并且**只认 embed_model 这一个模型名**。
"""

from __future__ import annotations

import requests

from app.core.config import settings

# 本地模型服务不走系统代理。
#
# 真实坑：机器上开着代理软件时，requests 默认会读 HTTP_PROXY 环境变量，
# 于是给 127.0.0.1 的请求也被送去代理 —— 代理帮不上忙，回一个 502。
# 结果就是「明明服务没起，却报 502 而不是连不上」，排查方向直接被带偏。
# 本地地址本来也不需要代理，所以这里干脆关掉。
_local_session = requests.Session()
_local_session.trust_env = False


class EmbeddingError(Exception):
    """嵌入这一步失败了。message 是能直接给人看的话。"""


class EmbeddingUnavailableError(EmbeddingError):
    """连不上本地嵌入服务（服务没起 / 地址不对）。"""


def embed_texts(texts: list[str]) -> list[list[float]]:
    """把一批文字各自变成一个向量。

    返回的第 i 项 = texts[i] 的向量，顺序不会乱。
    """
    if not texts:
        raise ValueError("没有要嵌入的文本")

    # 空串在这里就被本组件拦下，不会发给服务。
    # 说明：这是**本组件主动拒绝**，不是实测过"嵌入模型不支持空输入"——
    # 别的模型/服务可能接受空串并返回一个向量，那种向量的含义无法确认，
    # 所以这里统一在门口拦掉，而不是替所有嵌入模型下结论。
    cleaned = [(t or "").strip() for t in texts]
    if any(not t for t in cleaned):
        raise ValueError("文本里有空内容，本组件拒绝发送空输入")

    url = settings.ollama_base_url.rstrip("/") + "/api/embed"
    try:
        resp = _local_session.post(
            url,
            json={"model": settings.embed_model, "input": cleaned},
            timeout=120,
        )
        resp.raise_for_status()
    except requests.exceptions.ConnectionError as e:
        raise EmbeddingUnavailableError(f"连不上本地嵌入服务：{url}") from e
    except requests.exceptions.Timeout as e:
        raise EmbeddingError("嵌入请求超时（120 秒）") from e
    except requests.exceptions.HTTPError as e:
        code = e.response.status_code if e.response is not None else "未知"
        raise EmbeddingError(f"嵌入服务返回错误状态码 {code}") from e

    try:
        data = resp.json()
    except ValueError as e:
        # 服务端 MB 挂了一半会吐回 HTML 之类的东西，json 解析直接炸
        raise EmbeddingError("嵌入服务返回的不是合法 JSON") from e

    if not isinstance(data, dict):
        raise EmbeddingError("嵌入服务返回的不是一个 JSON 对象")

    vectors = data.get("embeddings")
    if not isinstance(vectors, list):
        raise EmbeddingError("返回里没有 embeddings 字段，或者它不是列表")
    if not vectors:
        raise EmbeddingError("返回的 embeddings 是空的")

    # 数量必须对得上。这一条最关键：
    # 下游 vector_search 是 zip(向量列表, 片段列表) 来配对的，
    # 少返回几个的话 zip 会**静默截断** —— 不报错、不少算，只是悄悄丢掉尾部几条，
    # 最后表现为"有几块资料从来没被检索到"，极难发现。
    if len(vectors) != len(cleaned):
        raise EmbeddingError(
            f"返回的向量数量与输入不一致："
            f"输入 {len(cleaned)} 条，返回 {len(vectors)} 条"
        )

    for i, v in enumerate(vectors):
        if not isinstance(v, list) or not v:
            raise EmbeddingError(f"第 {i} 个向量不是列表，或者它是空的")
        for x in v:
            # bool 是 int 的子类，但它不该出现在向量里，单独排除
            if isinstance(x, bool) or not isinstance(x, (int, float)):
                raise EmbeddingError(
                    f"第 {i} 个向量里有不是数字的分量：{type(x).__name__}"
                )

    dims = {len(v) for v in vectors}
    if len(dims) != 1:
        raise EmbeddingError(f"返回的向量维度不一致：{sorted(dims)}")

    return vectors


def embed_one(text: str) -> list[float]:
    """把一句话变成一个向量。只是 embed_texts 的单条包装。"""
    return embed_texts([text])[0]
