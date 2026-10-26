# -*- coding: utf-8 -*-
"""混合检索（RRF）的行为测试。

## 这份测试证明了什么、没证明什么

证明了（纯离线、全是人工排名或假嵌入）：
  - RRF 只按**名次**累加贡献，不把两种不同单位的分数混加
  - 零命中的关键词片段不会被白送奖励
  - 同名不同 doc_id 不会被合并
  - 空库、top_k 非法、并列稳定、异常传播这些边界行为正确

**没证明**：hybrid 比 vector 或 keyword 更好。
这里一次真实嵌入都没跑，也没有任何"检索质量提升"的证据。
要谈效果好坏，必须另做同一资料快照、同样问题、同样 top_k 的真实前后对照。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import ask_demo  # noqa: E402

from app.models.retrieval import Candidate, CorpusChunk  # noqa: E402
from app.services import embedder, retriever  # noqa: E402
from app.services.embedder import EmbeddingError  # noqa: E402
from app.services.retriever import RRF_K, hybrid_search, _rrf_fuse  # noqa: E402


def _chunk(doc_id: str, chunk_index: int, text: str, global_index: int = 0,
           filename: str | None = None) -> CorpusChunk:
    return CorpusChunk(
        global_index=global_index,
        doc_id=doc_id,
        filename=filename or f"{doc_id}.md",
        chunk_index=chunk_index,
        text=text,
    )


def _patch_embeddings(monkeypatch, vec=None):
    """把嵌入换成固定向量：全部相同 → 余弦全相等 → 顺序由 global_index 决定。"""
    vector = vec or [1.0, 0.0]
    monkeypatch.setattr(
        retriever, "embed_texts", lambda texts: [list(vector) for _ in texts]
    )


# ---------- 1. 纯融合：数值必须与公式一致 ----------

def test_rrf_scores_match_formula_exactly():
    """规格场景：关键词 A第1、B第2；向量 B第1、C第2。"""
    a = _chunk("d-A", 0, "甲的内容")
    b = _chunk("d-B", 0, "乙的内容")
    c = _chunk("d-C", 0, "丙的内容")

    fused = _rrf_fuse([[a, b], [b, c]])
    scores = {ch.doc_id: score for score, ch in fused}

    assert RRF_K == 60
    assert scores["d-A"] == pytest.approx(1 / 61)
    assert scores["d-B"] == pytest.approx(1 / 62 + 1 / 61)
    assert scores["d-C"] == pytest.approx(1 / 62)


def test_rrf_ranking_puts_dually_recommended_first():
    a = _chunk("d-A", 0, "甲")
    b = _chunk("d-B", 0, "乙")
    c = _chunk("d-C", 0, "丙")

    fused = _rrf_fuse([[a, b], [b, c]])
    fused.sort(key=lambda pair: -pair[0])

    assert [ch.doc_id for _, ch in fused] == ["d-B", "d-A", "d-C"]


def test_absent_from_a_list_contributes_zero():
    """某一路没出现就是 0，不需要额外的“补零”逻辑。"""
    a = _chunk("d-A", 0, "甲")
    fused = _rrf_fuse([[a], []])
    assert fused[0][0] == pytest.approx(1 / 61)


def test_duplicate_in_the_same_list_counts_only_once():
    a = _chunk("d-A", 0, "甲")
    fused = _rrf_fuse([[a, a]])
    assert fused[0][0] == pytest.approx(1 / 61), "同一路里重复出现不能叠加两次"


# ---------- 2. 去重键必须用 doc_id，不能用 filename ----------

def test_same_filename_different_doc_id_is_not_merged():
    a = _chunk("doc-1", 0, "甲", filename="笔记.md")
    b = _chunk("doc-2", 0, "乙", filename="笔记.md")

    fused = _rrf_fuse([[a, b]])

    assert len(fused) == 2, "两个都叫笔记.md 的第0块不是同一份资料，不能被合并"


def test_same_chunk_from_two_lists_is_merged_and_scores_add_up():
    a1 = _chunk("doc-1", 0, "甲")
    a2 = _chunk("doc-1", 0, "甲")

    fused = _rrf_fuse([[a1], [a2]])

    assert len(fused) == 1
    assert fused[0][0] == pytest.approx(1 / 61 + 1 / 61)


# ---------- 3. 并列时用 global_index 稳定决胜 ----------

def test_tied_scores_break_by_global_index():
    """两路名次对称 → 分数相等 → 由 global_index 决定，而不是随机。"""
    x = _chunk("d-X", 0, "甲", global_index=1)
    y = _chunk("d-Y", 0, "乙", global_index=0)

    fused = _rrf_fuse([[x, y], [y, x]])

    # 分数确实相等
    scores = [s for s, _ in fused]
    assert scores[0] == pytest.approx(scores[1])

    candidates = hybrid_search.__globals__["_to_candidates"](fused, 2)
    order = [c.doc_id for c in candidates]
    assert order == ["d-Y", "d-X"], "并列时应按 global_index 从小到大，结果必须稳定"


# ---------- 4. hybrid_search 的边界 ----------

def test_empty_corpus_returns_empty_without_touching_embedding(monkeypatch):
    called = []

    def _should_not_run(texts):
        called.append(1)
        return [[1.0, 0.0] for _ in texts]

    monkeypatch.setattr(retriever, "embed_texts", _should_not_run)

    assert hybrid_search("随便问一句", [], 3) == []
    assert called == [], "空库时不应发出任何嵌入请求"


@pytest.mark.parametrize("bad_top_k", [0, -1, True])
def test_non_positive_or_bool_top_k_is_rejected(bad_top_k):
    corpus = [_chunk("d-A", 0, "甲")]

    with pytest.raises(ValueError, match="正整数"):
        hybrid_search("问一句", corpus, bad_top_k)


def test_hybrid_filters_zero_score_keyword_hits(monkeypatch):
    """完全没命中的片段，不能因为排在关键词列表里就白拿一份贡献。

    断言落到分数上：
      - 过滤了的话，zero 只有向量那路的 1/61
      - 没过滤的话，它还会多拿一份关键词的贡献
    """
    zero = _chunk("d-zero", 0, "完全无关的一段话。", global_index=0)
    hit = _chunk("d-hit", 0, "这里写着版本信息。", global_index=1)

    _patch_embeddings(monkeypatch)  # 向量全同 → 顺序按 global_index

    result = hybrid_search("版本信息", [zero, hit], 3)
    by_doc = {c.doc_id: c.score for c in result}

    assert by_doc["d-zero"] == pytest.approx(round(1 / 61, 4)), (
        "零命中的片段拿到了关键词那一路的贡献，说明混合分支没过滤 0 分项"
    )
    assert by_doc["d-hit"] == pytest.approx(round(1 / 61 + 1 / 62, 4))


def test_hybrid_propagates_embedding_error_instead_of_degrading(monkeypatch):
    """向量这路失败时必须报错，不能静默退化成关键词还自称 hybrid。"""

    def _boom(*a, **kw):
        raise EmbeddingError("嵌入服务不可用（测试注入）")

    monkeypatch.setattr(retriever, "vector_search", _boom)

    with pytest.raises(EmbeddingError, match="测试注入"):
        hybrid_search("问一句", [_chunk("d-A", 0, "甲")], 3)


# ---------- 5. hybrid_search 确实走现有检索路径 ----------

def test_hybrid_fuses_both_existing_paths_by_rank(monkeypatch):
    """用人为排名代替真实检索，确认两路都被调用且按名次融合。"""
    corpus = [
        _chunk("d-A", 0, "甲", global_index=0),
        _chunk("d-B", 0, "乙", global_index=1),
        _chunk("d-C", 0, "丙", global_index=2),
    ]
    calls = []

    def fake_keyword(question, c, top_k):
        calls.append(("keyword", top_k))
        return [
            Candidate(rank=1, score=5.0, chunk_index=0, doc_id="d-A",
                      filename="a.md", text="甲"),
            Candidate(rank=2, score=2.0, chunk_index=0, doc_id="d-B",
                      filename="b.md", text="乙"),
        ]

    def fake_vector(question, c, top_k):
        calls.append(("vector", top_k))
        return [
            Candidate(rank=1, score=0.90, chunk_index=0, doc_id="d-B",
                      filename="b.md", text="乙"),
            Candidate(rank=2, score=0.80, chunk_index=0, doc_id="d-C",
                      filename="c.md", text="丙"),
        ]

    monkeypatch.setattr(retriever, "keyword_search", fake_keyword)
    monkeypatch.setattr(retriever, "vector_search", fake_vector)

    result = hybrid_search("问一句", corpus, 3)

    assert [name for name, _ in calls] == ["keyword", "vector"], "两路都应被调用"
    assert [c.doc_id for c in result] == ["d-B", "d-A", "d-C"]
    assert result[0].rank == 1 and result[2].rank == 3, "融合后 rank 必须重新编号"


def test_hybrid_uses_window_not_bare_top_k(monkeypatch):
    """每一路的窗口是 min(len(corpus), max(10, top_k))，不是直接 top_k。"""
    corpus = [_chunk(f"d-{i}", 0, f"第{i}块内容", global_index=i) for i in range(20)]
    seen_windows = []

    def fake_keyword(question, c, top_k):
        seen_windows.append(("keyword", top_k))
        return [Candidate(rank=1, score=1.0, chunk_index=0, doc_id="d-0",
                          filename="a.md", text="甲")]

    def fake_vector(question, c, top_k):
        seen_windows.append(("vector", top_k))
        return [Candidate(rank=1, score=0.9, chunk_index=0, doc_id="d-0",
                          filename="a.md", text="甲")]

    monkeypatch.setattr(retriever, "keyword_search", fake_keyword)
    monkeypatch.setattr(retriever, "vector_search", fake_vector)

    hybrid_search("问一句", corpus, 3)

    # min(20, max(10, 3)) == 10
    assert seen_windows == [("keyword", 10), ("vector", 10)]


# ---------- 6. CLI：--mode hybrid 与失败信息 ----------

def test_cli_hybrid_mode_routes_to_hybrid_search(monkeypatch, capsys):
    used = []

    def fake_hybrid(question, corpus, top_k):
        used.append(top_k)
        return [
            Candidate(rank=1, score=0.03, chunk_index=0, doc_id="d-A",
                      filename="a.md", text="甲的内容")
        ]

    monkeypatch.setattr(ask_demo, "load_corpus", lambda: [])
    monkeypatch.setattr(ask_demo, "hybrid_search", fake_hybrid)
    monkeypatch.setattr(ask_demo, "generate", lambda *a, **k: ("假回答", 1, 0.1))
    monkeypatch.setattr(sys, "argv", ["ask_demo.py", "问一句", "--mode", "hybrid"])

    ask_demo.main()

    assert used == [3], "--mode hybrid 应调用 hybrid_search"


def test_cli_reports_embedding_failure_and_skips_the_model(monkeypatch, capsys):
    """嵌入失败要给出准确原因，且绝对不能继续调用模型。"""
    called = []

    def _boom(*a, **kw):
        raise EmbeddingError("连不上本地嵌入服务：http://127.0.0.1:11434/api/embed")

    monkeypatch.setattr(ask_demo, "load_corpus", lambda: [_chunk("d-A", 0, "甲")])
    monkeypatch.setattr(ask_demo, "vector_search", _boom)
    monkeypatch.setattr(
        ask_demo, "generate", lambda *a, **k: called.append(1) or ("答案", 1, 0.1)
    )
    monkeypatch.setattr(sys, "argv", ["ask_demo.py", "问一句"])

    ask_demo.main()

    out = capsys.readouterr().out
    assert "嵌入失败" in out
    assert called == [], "嵌入失败时不该调用模型"
