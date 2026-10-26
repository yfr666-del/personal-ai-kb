# -*- coding: utf-8 -*-
"""检索对照入口：同一批资料、同一个问题，让两种检索各跑一遍。

在项目根目录执行：
    .venv\\Scripts\\python.exe scripts\\retrieve_demo.py

它做三件事：
    1. 把磁盘上的真实片段读成一个检索库
    2. 对每个问题分别跑关键词检索和向量检索，把候选并排打印出来
    3. 跑几个失败场景，确认出错时是"说清楚为什么"，而不是"崩掉"

看结果时注意：**分数高不等于答案对**。
这里打印的分数只用来看排序，不用来判断有没有答案。
"""

from __future__ import annotations

import sys
from pathlib import Path

# 直接执行 scripts/*.py 时，Python 会把 scripts/ 当成查找起点，
# 那样 import app 会失败。这里把项目根目录补进搜索路径。
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.core.config import settings
from app.models.retrieval import Candidate
from app.services.embedder import (
    EmbeddingError,
    EmbeddingUnavailableError,
    embed_texts,
)
from app.services.retriever import (
    cosine_similarity,
    keyword_search,
    load_corpus,
    vector_search,
)

TOP_K = 3

# 五个固定的验证问题，各测一种情况
QUESTIONS = [
    ("pytest", "字面匹配：这个词直接写在资料里"),
    ("怎么跑测试", "换个说法：资料里写的是 pytest -v，没有「跑测试」三个字连续出现"),
    ("v0.1.0", "精确版本号：一串没有任何语义的数字"),
    ("文档元数据的校验规则写在哪个文件", "语义 + 精确路径：答案是 app/models/document.py"),
    ("我用的显卡型号是什么", "资料里没有答案：看两种检索会不会硬凑"),
]


def _print_candidates(title: str, cands: list[Candidate]) -> None:
    print("  【" + title + "】")
    if not cands:
        print("    （没有候选）")
        return
    for c in cands:
        head = c.text.strip().replace("\n", " / ")[:46]
        print(f"    {c.rank}. 分数={c.score:<8} 来源={c.filename}#chunk{c.chunk_index}")
        print(f"       文档id={c.doc_id}")
        print(f"       原文  ={head}")


def _section(title: str) -> None:
    print()
    print("=" * 62)
    print(title)
    print("=" * 62)


def main() -> None:
    # Windows 中文终端默认是 GBK，打印 Unicode 方块字符会炸，改一次就好
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    corpus = load_corpus()
    print("检索库里有 " + str(len(corpus)) + " 个片段，来自 " +
          str(len({c.doc_id for c in corpus})) + " 个文档")

    files = sorted({c.filename for c in corpus})
    print("文档文件名：" + "、".join(files))

    _section("第一部分：同一个问题，两种检索")
    for question, why in QUESTIONS:
        print()
        print("问题：" + question)
        print("  （这一题要看：" + why + "）")
        _print_candidates("关键词检索", keyword_search(question, corpus, TOP_K))
        try:
            _print_candidates("向量检索", vector_search(question, corpus, TOP_K))
        except EmbeddingError as e:
            print("  向量检索没跑起来：" + str(e))

    _section("第二部分：失败场景")
    _check("1. 空输入", _case_empty_input)
    _check("2. 维度不一致", _case_dim_mismatch)
    _check("3. 服务不可用", _case_service_down)
    _check("4. 空检索库", _case_empty_corpus)

    _section("补充核实：聊天模型能不能当嵌入模型用")
    _case_chat_model_as_embedder()


def _check(title: str, fn) -> None:
    print()
    print(title)
    try:
        result = fn()
        print("  结果：" + result)
    except Exception as e:  # noqa: BLE001 - demo 里就是要看看各种错会长什么样
        print(f"  抛出 {type(e).__name__}：{e}")


def _case_empty_input() -> str:
    try:
        embed_texts([""])
    except ValueError as e:
        return "被拦住了（ValueError）：" + str(e)
    return "没有被拦住 —— 这是个问题"


def _case_dim_mismatch() -> str:
    cosine_similarity([1.0, 2.0], [1.0, 2.0, 3.0])
    return "没有报错 —— 这是个问题"


def _case_service_down() -> str:
    # 临时把地址指到一个没人监听的端口，用完必须还原
    original = settings.ollama_base_url
    settings.ollama_base_url = "http://127.0.0.1:59999"
    try:
        embed_texts(["随便一句话"])
    except EmbeddingUnavailableError as e:
        return "报的是 EmbeddingUnavailableError：" + str(e)
    except EmbeddingError as e:
        return "报的是 EmbeddingError：" + str(e)
    finally:
        settings.ollama_base_url = original
    return "没报错 —— 这是个问题"


def _case_empty_corpus() -> str:
    cands = vector_search("随便问一句", [], TOP_K)
    return f"返回 {len(cands)} 个候选（期望 0）"


def _case_chat_model_as_embedder() -> None:
    """拿聊天模型 qwen3:4b 去请求嵌入，看它到底给不给。

    这一条是为了落实"不要把聊天模型当成嵌入模型"——
    不是凭感觉说它不行，是实跑一遍看它返回什么。
    """
    print()
    print("聊天模型：" + settings.llm_model + " / 嵌入模型：" + settings.embed_model)

    import requests

    # 同样关掉代理：这是给本地服务发的请求，走代理只会拿到假的 502
    session = requests.Session()
    session.trust_env = False

    url = settings.ollama_base_url.rstrip("/") + "/api/embed"
    try:
        resp = session.post(
            url,
            json={"model": settings.llm_model, "input": ["测试一句话"]},
            timeout=60,
        )
        print("  HTTP 状态码：" + str(resp.status_code))
        print("  返回体前 200 字符：" + resp.text[:200])
    except Exception as e:  # noqa: BLE001
        print(f"  请求就没发出去：{type(e).__name__}：{e}")


if __name__ == "__main__":
    main()
