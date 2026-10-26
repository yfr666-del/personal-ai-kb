# -*- coding: utf-8 -*-
"""命令行问答闭环：问题 → 检索候选 → 把候选交给 qwen3:4b → 打印回答。

这是检索接入回答链路的**最小形态**：
没有界面、没有框架、没有"相似度低于多少就拒答"的阈值。

    用法（在项目根目录）：
        .venv\\Scripts\\python.exe scripts\\ask_demo.py "切分是怎么做的？"
        .venv\\Scripts\\python.exe scripts\\ask_demo.py "切分是怎么做的？" --mode keyword

    两个开关：
        --mode vector（默认）/ keyword / hybrid：用哪种检索挑候选
        --top-k N：挑几条候选（默认 3）

    hybrid 是**实验性**的：它用 RRF 把关键词和向量两路的**名次**融合起来。
    存在 ≠ 更好 —— 本轮没有跑过真实资料的前后对照，没有"它更强"的证据。

**三点要说在前面：**

1. **会给模型看的片段，脚本会原样打印出来。**
   "模型到底读了什么"必须能直接看到 —— 不然就没法判断它的回答有没有依据。
   每条都带 `[文件名#第几块]` 的来源标识，能拿这个标识回磁盘找原文。

2. **本脚本不保证模型会拒答。**
   即使资料里没有答案，它也可能照答不误（实测过：问"显卡型号"，
   检索同样返回了候选）。脚本只负责"把候选给它、把话带回来"，
   不替模型判断该不该答，也不设阈值拦截。

3. **候选 ≠ 答案。** 检索只是"挑出可能相关的几块"，
   至于里面有没有答案，得你自己看下面打印出来的原文。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 直接执行 scripts/*.py 时 Python 会把 scripts/ 当查找起点，补上项目根目录
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.core.config import settings  # noqa: E402
from app.services.embedder import EmbeddingError  # noqa: E402
from app.services.generator import GenerationError, generate  # noqa: E402
from app.services.retriever import (  # noqa: E402
    hybrid_search,
    keyword_search,
    load_corpus,
    vector_search,
)

SYSTEM_TEXT = (
    "你是一个严谨的助手。只根据下面给出的资料回答。"
    "资料里没有的，就回答「资料里没有」。"
)


def _build_prompt(candidates, question:str) -> str:
    """把候选拼成模型能看懂的一段话，每条带上来源标识。"""
    lines = ["下面是检索出来的资料片段，每条开头的方括号是它的来源：", ""]
    for c in candidates:
        lines.append(f"[{c.filename}#{c.chunk_index}] {c.text.strip()}")
    lines.append("")
    lines.append("请只根据以上资料回答问题。")
    lines.append(f"问题：{question}")
    return "\n".join(lines)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="检索 + 生成的最小命令行闭环")
    parser.add_argument("question", help="要问的问题")
    parser.add_argument(
        "--mode", choices=["vector", "keyword", "hybrid"], default="vector",
        help="用哪种检索挑候选（默认 vector）；hybrid 是实验性的 RRF 混合",
    )
    parser.add_argument("--top-k", type=int, default=3, help="挑几条候选（默认 3）")
    parser.add_argument(
        "--debug", action="store_true",
        help="打印实际发送给模型的完整 system / user 消息（回答不对时先看这个）",
    )
    args = parser.parse_args()

    corpus = load_corpus()
    print("=" * 62)
    print(f"问题：{args.question}")
    print(f"检索方式：{args.mode} / 候选数：{args.top_k} / 库里有 {len(corpus)} 个片段")
    print("=" * 62)

    # 嵌入失败要在这里说清楚，不能让它冒成 traceback 之后还继续跑；
    # 也不捕获 generator 的异常 —— 那是另一层的事，保持各自的错误策略。
    try:
        if args.mode == "keyword":
            candidates = keyword_search(args.question, corpus, args.top_k)
        elif args.mode == "hybrid":
            candidates = hybrid_search(args.question, corpus, args.top_k)
        else:
            candidates = vector_search(args.question, corpus, args.top_k)
    except EmbeddingError as e:
        print()
        print(f"嵌入失败：{e}")
        print()
        print("这一步是「把文字变成向量」，失败意味着候选根本没有排出来。")
        print("后面不会调用模型，也不会产生任何分数或回答。")
        return

    print()
    print(">>> 下面这些片段会被原样交给模型 <<<")
    if not candidates:
        print("（没有候选 —— 库是空的）")
        return
    for c in candidates:
        print(f"  来源 [{c.filename}#{c.chunk_index}]  分数 {c.score}  名次 {c.rank}")
        print(f"    文档id = {c.doc_id}")
        print(f"    原文预览（前 80 字，不是全文）= {c.text.strip()[:80]}")
    print()
    print("注意：上面只是预览（每条只截了前 80 字），模型收到的是片段全文；")
    print("      想看模型实际收到的完整消息，运行时加 --debug。")
    print("      另外：以上是「检索到的候选」，不等于「答案在里面」。")

    prompt = _build_prompt(candidates, args.question)

    if args.debug:
        print()
        print("=" * 62)
        print(">>> 调试：下面两段就是实际发给模型的完整消息 <<<")
        print("=" * 62)
        print("--- system ---")
        print(SYSTEM_TEXT)
        print("--- user ---")
        print(prompt)
        print("--- user 结束 ---")
    print()
    print("=" * 62)
    print(f"交给模型：{settings.llm_model}")
    print("=" * 62)

    try:
        content, tokens, seconds = generate(prompt, system_text=SYSTEM_TEXT)
    except GenerationError as e:
        print(f"模型调用失败：{e}")
        return

    print()
    print("回答 =")
    print(content)
    print()
    print(f"（输出 token {tokens} / 服务端总计 {seconds} 秒）")


if __name__ == "__main__":
    main()
