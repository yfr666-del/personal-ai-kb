# -*- coding: utf-8 -*-
"""检索链路新增行为的断言测试。

这些测试**不依赖本地模型服务在跑**：
用 monkeypatch 把 embedder 里的会话替换掉，直接喂给它各种返回体，
看它是不是按预期通过 / 报错。

跟 scripts/retrieve_demo.py 里那几个"打印出来看看"的场景不一样 ——
那里只是演示，捕获到异常打印一行**不等于**测试通过；
这里每一条都得真的断言。
"""

from __future__ import annotations

import math

import pytest
import requests

from app.services import embedder
from app.services.embedder import EmbeddingError, EmbeddingUnavailableError, embed_texts
from app.services.retriever import cosine_similarity, keyword_search, vector_search


class _FakeResponse:
    """假的 requests 响应，只需要 embedder 用到的那几个东西。"""

    def __init__(self, payload, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(
                f"{self.status_code} Client Error", response=self
            )

    def json(self):
        return self._payload


def _patch(monkeypatch, payload, status_code: int = 200):
    """把 embedder 的会话 post 换成返回固定 payload 的假函数。"""
    monkeypatch.setattr(
        embedder._local_session,
        "post",
        lambda *a, **kw: _FakeResponse(payload, status_code),
    )


# ---------- embedder：本组件主动拒绝 ----------

def test_empty_text_is_rejected_before_sending(monkeypatch):
    """空输入应该在发出请求之前就被拦下，根本不该走到 post。"""
    called = []

    def _should_not_be_called(*a, **kw):
        called.append(1)
        return _FakeResponse({"embeddings": [[0.1, 0.2]]})

    monkeypatch.setattr(embedder._local_session, "post", _should_not_be_called)

    with pytest.raises(ValueError, match="空内容"):
        embed_texts([""])
    with pytest.raises(ValueError, match="空内容"):
        embed_texts(["有内容", "   "])
    assert called == [], "空输入不应该发出任何请求"


def test_empty_list_is_rejected():
    with pytest.raises(ValueError, match="没有要嵌入的文本"):
        embed_texts([])


# ---------- embedder：返回体的各种坏情况 ----------

def test_missing_embeddings_field(monkeypatch):
    _patch(monkeypatch, {"something_else": []})
    with pytest.raises(EmbeddingError, match="没有 embeddings"):
        embed_texts(["一句话"])


def test_embeddings_not_a_list(monkeypatch):
    _patch(monkeypatch, {"embeddings": {"a": 1}})
    with pytest.raises(EmbeddingError, match="不是列表"):
        embed_texts(["一句话"])


def test_empty_embeddings(monkeypatch):
    _patch(monkeypatch, {"embeddings": []})
    with pytest.raises(EmbeddingError, match="是空的"):
        embed_texts(["一句话"])


def test_count_mismatch_is_rejected(monkeypatch):
    """这条最关键：数量对不上时 zip 会静默截断，必须在这里拦住。"""
    _patch(monkeypatch, {"embeddings": [[0.1, 0.2], [0.3, 0.4]]})  # 只给 2 条
    with pytest.raises(EmbeddingError, match="数量与输入不一致"):
        embed_texts(["一", "二", "三"])  # 要 3 条


def test_too_many_vectors_is_rejected(monkeypatch):
    """多给也算不一致 —— 不能只防少给。"""
    _patch(monkeypatch, {"embeddings": [[0.1], [0.2], [0.3]]})
    with pytest.raises(EmbeddingError, match="数量与输入不一致"):
        embed_texts(["只有一句"])


def test_non_numeric_component_is_rejected(monkeypatch):
    _patch(monkeypatch, {"embeddings": [[0.1, "不是数字"]]})
    with pytest.raises(EmbeddingError, match="不是数字"):
        embed_texts(["一句话"])


def test_bool_component_is_rejected(monkeypatch):
    """bool 是 int 的子类，但不该混进向量里。"""
    _patch(monkeypatch, {"embeddings": [[0.1, True]]})
    with pytest.raises(EmbeddingError, match="不是数字"):
        embed_texts(["一句话"])


def test_vector_not_a_list(monkeypatch):
    _patch(monkeypatch, {"embeddings": [0.5]})
    with pytest.raises(EmbeddingError, match="不是列表"):
        embed_texts(["一句话"])


def test_empty_vector_is_rejected(monkeypatch):
    _patch(monkeypatch, {"embeddings": [[]]})
    with pytest.raises(EmbeddingError, match="不是列表，或者它是空的"):
        embed_texts(["一句话"])


def test_dim_mismatch_is_rejected(monkeypatch):
    _patch(monkeypatch, {"embeddings": [[0.1, 0.2], [0.3]]})
    with pytest.raises(EmbeddingError, match="维度不一致"):
        embed_texts(["一", "二"])


def test_http_error_status(monkeypatch):
    _patch(monkeypatch, {"error": "boom"}, status_code=500)
    with pytest.raises(EmbeddingError, match="错误状态码 500"):
        embed_texts(["一句话"])


def test_connection_error_becomes_unavailable(monkeypatch):
    def _boom(*a, **kw):
        raise requests.exceptions.ConnectionError("连不上")

    monkeypatch.setattr(embedder._local_session, "post", _boom)
    with pytest.raises(EmbeddingUnavailableError):
        embed_texts(["一句话"])


def test_normal_response_passes(monkeypatch):
    """好返回体要能正常通过，并且条数、维度与输入对得上。"""
    _patch(monkeypatch, {"embeddings": [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]})
    result = embed_texts(["第一句", "第二句"])
    assert len(result) == 2
    assert all(len(v) == 3 for v in result)
    assert result[0] == [0.1, 0.2, 0.3]


# ---------- 余弦相似度 ----------

def test_cosine_dim_mismatch_raises():
    with pytest.raises(ValueError, match="维度不一致"):
        cosine_similarity([1.0, 2.0], [1.0, 2.0, 3.0])


def test_cosine_zero_vector_is_zero():
    assert cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0


def test_cosine_identical_is_one():
    assert math.isclose(cosine_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]), 1.0)


def test_cosine_orthogonal_is_zero():
    assert math.isclose(cosine_similarity([1.0, 0.0], [0.0, 1.0]), 0.0)


# ---------- 检索：空库与空输入 ----------

def test_vector_search_empty_corpus_returns_empty(monkeypatch):
    """空库不该去调嵌入服务 —— 直接返回空。"""
    called = []
    monkeypatch.setattr(
        embedder._local_session,
        "post",
        lambda *a, **kw: (called.append(1), _FakeResponse({"embeddings": [[0.1]]}))[1],
    )
    assert vector_search("随便问一句", []) == []
    assert called == [], "空库时不应该发出嵌入请求"


def test_keyword_search_empty_corpus_returns_empty():
    assert keyword_search("随便问一句", []) == []
