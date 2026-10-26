# -*- coding: utf-8 -*-
"""RAG 输入构造回归检查（E01/E02/E03 起步样本）。

**这份测试检查到哪一层，必须先说清楚：**

    ✅ 真实函数的提示词构造（`scripts/ask_demo.py` 的 `_build_prompt`）
    ✅ 真实函数的请求体构造（`app/services/generator.py` 的 `generate`）
    ❌ 不调用真实模型 —— post 被 monkeypatch 换成固定假响应
    ❌ 不读取主项目真实 data 目录 —— 资料全是内存里构造的公开教学资料

**mock 通过只证明「请求装对了」，不证明模型能答对。**

样本状态一律区分：`prompt_check` / `retrieval_check` / `answer_check`。
离线未跑的真实检索与生成，在 `rag_cases_v1.json` 里标 `not_run`，
不填零分冒充失败，也不填通过。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ask_demo.py 在 scripts/ 下（不是包），把目录显式加进来才能 import
_SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import ask_demo  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.models.retrieval import Candidate  # noqa: E402
from app.services import generator  # noqa: E402

CASES_PATH = PROJECT_ROOT / "learning" / "evaluation" / "rag_cases_v1.json"


# ---------- 样本装载 ----------

def _load_spec() -> dict:
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))


def _demo_candidates() -> list[Candidate]:
    """把 JSON 里的公开教学资料转成真实 Candidate。"""
    spec = _load_spec()
    return [
        Candidate(
            rank=i + 1,
            score=round(1.0 - i * 0.1, 4),
            chunk_index=item["chunk_index"],
            doc_id=item["doc_id"],
            filename=item["filename"],
            text=item["text"],
        )
        for i, item in enumerate(spec["sources"])
    ]


def _case_questions() -> list[str]:
    return [c["question"] for c in _load_spec()["cases"]]


# ---------- 1. 同一候选换问题：两份 prompt 必须不同 ----------

def test_same_candidates_different_questions_produce_different_prompts():
    candidates = _demo_candidates()
    questions = _case_questions()

    prompts = [ask_demo._build_prompt(candidates, q) for q in questions]

    assert len(set(prompts)) == len(questions), (
        "不同问题拼出了相同的提示词，说明问题没有真正进入提示词"
    )


def test_each_prompt_contains_its_own_full_question_line():
    candidates = _demo_candidates()

    for question in _case_questions():
        prompt = ask_demo._build_prompt(candidates, question)
        assert f"问题：{question}" in prompt, f"提示词缺少完整问题行：{question}"


def test_prompt_does_not_leak_other_questions():
    """换问题时不能把别的问题混进来 —— 否则「不同」就是假的。"""
    candidates = _demo_candidates()
    questions = _case_questions()

    for question in questions:
        prompt = ask_demo._build_prompt(candidates, question)
        for other in questions:
            if other != question:
                assert f"问题：{other}" not in prompt


# ---------- 2. 来源与完整片段保留 ----------

def test_every_source_marker_is_present():
    candidates = _demo_candidates()
    prompt = ask_demo._build_prompt(candidates, _case_questions()[0])

    for c in candidates:
        assert f"[{c.filename}#{c.chunk_index}]" in prompt, (
            f"来源标识缺失：{c.filename}#{c.chunk_index}"
        )


def test_full_chunk_text_is_preserved():
    candidates = _demo_candidates()
    prompt = ask_demo._build_prompt(candidates, _case_questions()[0])

    for c in candidates:
        assert c.text.strip() in prompt, f"片段正文没有完整进入提示词：{c.doc_id}"


def test_text_beyond_80_chars_is_not_truncated():
    """CLI 那段「前 80 字预览」是给人看的；提示词里必须是全文。"""
    tail = "后缀标记_BEYOND_80_CHARS"
    long_text = "甲" * 100 + tail

    assert len(long_text) > 80, "这段测试数据本身必须超过 80 字才有意义"

    long_candidate = Candidate(
        rank=1, score=0.9, chunk_index=7,
        doc_id="demo-long", filename="demo-long.md", text=long_text,
    )
    prompt = ask_demo._build_prompt([long_candidate], "长文本去哪了？")

    assert tail in prompt, "80 字之后的内容被截断了，提示词拿到的不是片段全文"


# ---------- 3. 空候选：不编造资料，也不凭空给答案 ----------

def test_empty_candidates_does_not_fabricate_evidence():
    question = "演示版本是多少？"
    prompt = ask_demo._build_prompt([], question)

    assert f"问题：{question}" in prompt, "没有候选时问题本体仍应存在"

    for item in _load_spec()["sources"]:
        assert item["text"].strip() not in prompt, (
            "候选为空时，提示词里不该出现任何资料正文"
        )

    assert "v0.1.0" not in prompt, "没有资料时不该凭空冒出答案文本"


# ---------- 4. CLI 空库：不能走到 generate ----------

def test_cli_empty_corpus_does_not_reach_generate(monkeypatch, capsys):
    called = []

    monkeypatch.setattr(ask_demo, "load_corpus", lambda: [])
    monkeypatch.setattr(ask_demo, "keyword_search", lambda *a, **kw: [])
    monkeypatch.setattr(ask_demo, "vector_search", lambda *a, **kw: [])

    def _should_not_run(*a, **kw):
        called.append(1)
        return ("假回答", 1, 0.1)

    monkeypatch.setattr(ask_demo, "generate", _should_not_run)
    monkeypatch.setattr(sys, "argv", ["ask_demo.py", "演示版本是多少？"])

    ask_demo.main()

    assert called == [], "库是空的时候，CLI 不该调用 generate"
    assert "没有候选" in capsys.readouterr().out


# ---------- 5. generate 的请求体构造（mock post，不发真实请求） ----------

class _FakeResponse:
    """假的 requests 响应：只提供 raise_for_status 与 json。"""

    def __init__(self, payload, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError("boom", response=self)

    def json(self):
        return self._payload


@pytest.fixture
def captured_payload(monkeypatch):
    """把 generator 的 post 换成假函数，记录发出去的 payload。"""
    captured: dict = {}

    monkeypatch.setattr(settings, "ollama_base_url", "http://127.0.0.1:59999")
    monkeypatch.setattr(settings, "llm_model", "fake-model-for-test")

    def fake_post(url, json=None, timeout=None, **kwargs):
        captured["url"] = url
        captured["payload"] = json
        return _FakeResponse(
            {
                "message": {"content": "假回答"},
                "eval_count": 7,
                "total_duration": 2_000_000_000,
            }
        )

    monkeypatch.setattr(generator._local_session, "post", fake_post)
    return captured


def test_generate_payload_has_model_messages_and_stream(captured_payload):
    prompt = ask_demo._build_prompt(_demo_candidates(), "演示版本是多少？")

    generator.generate(prompt, system_text=ask_demo.SYSTEM_TEXT)

    payload = captured_payload["payload"]
    assert payload["model"] == "fake-model-for-test"
    assert payload["stream"] is False
    assert captured_payload["url"].endswith("/api/chat")


def test_system_present_still_keeps_question_and_evidence_in_user(captured_payload):
    """有 system 时，用户消息里仍需同时带着问题和资料。"""
    question = "演示版本是多少？"
    prompt = ask_demo._build_prompt(_demo_candidates(), question)

    generator.generate(prompt, system_text=ask_demo.SYSTEM_TEXT)

    messages = captured_payload["payload"]["messages"]
    assert [m["role"] for m in messages] == ["system", "user"]
    assert messages[0]["content"] == ask_demo.SYSTEM_TEXT

    user_content = messages[1]["content"]
    assert f"问题：{question}" in user_content
    assert "这是一个教学知识库，演示版本为v0.1.0。" in user_content
    assert "[demo-overview.md#0]" in user_content


def test_without_system_there_is_only_one_user_message(captured_payload):
    question = "演示版本是多少？"
    prompt = ask_demo._build_prompt(_demo_candidates(), question)

    generator.generate(prompt)

    messages = captured_payload["payload"]["messages"]
    assert [m["role"] for m in messages] == ["user"]
    assert f"问题：{question}" in messages[0]["content"]


def test_generate_return_semantics_unchanged(captured_payload):
    prompt = ask_demo._build_prompt(_demo_candidates(), "演示版本是多少？")

    content, tokens, seconds = generator.generate(prompt, system_text=ask_demo.SYSTEM_TEXT)

    assert content == "假回答"
    assert tokens == 7
    assert seconds == 2.0


# ---------- 6. 样本文件自身的一致性 ----------

def test_case_file_marks_offline_items_as_not_run():
    """防止有人把「还没跑真实检索/生成」的题偷偷标成通过。"""
    for case in _load_spec()["cases"]:
        assert case["retrieval_status"] == "not_run", f"{case['id']} 的真实检索尚未运行"
        assert case["answer_status"] == "not_run", f"{case['id']} 的真实生成尚未运行"


def test_unanswerable_case_is_excluded_from_hit_rate_denominator():
    cases = _load_spec()["cases"]
    answerable = [c for c in cases if c["has_answer"]]

    assert len(answerable) == 2, "有答案的题应为 2 道"
    e03 = next(c for c in cases if c["id"] == "E03")
    assert e03["has_answer"] is False
    assert e03["supporting_sources"] == []
