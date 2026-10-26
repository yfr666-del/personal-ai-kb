# -*- coding: utf-8 -*-
r"""
S3：让程序自己挑出相关的资料

它干什么：
    资料有很多条，问题只有一个。
    不可能每次都把全部资料塞进请求（慢、贵、还容易答偏）。
    所以先让程序算一算：哪几条跟这个问题最相关？只把那几条塞进去。
    这一步就叫「检索」。

怎么用（在项目根目录执行）：
    .venv\Scripts\python.exe learning\s3_retrieve.py

想改问题：
    只改下面 QUESTION 那一行引号里的字。
"""

import os
import subprocess
import sys
import time

import requests

# ============================================================ 你要改的地方
QUESTION = "切分是怎么做的？"
# ============================================================

# 资料：8 条笔记，每条一个编号
LINES = [
    "[1] 项目名称是 personal-ai-kb（个人 AI 知识库系统）。",
    "[2] 当前状态：M1 骨架 v0.1（tag v0.1.0），已打通「收资料」全链路。",
    "[3] 技术栈：Python 3.13、Pydantic v2、FastAPI、Uvicorn、pypdf、Streamlit、pytest。",
    "[4] 下一步（未完成）：M2 RAG 最简闭环 + 20 题评估集。",
    "[5] 我的目标：2027 年 8 月前拿到日薪 325 元以上的技术实习。",
    "[6] 切分策略：滑动窗口，窗口 500 字，重叠 100 字，优选切口为句号或换行。",
    "[7] 解析支持三种格式：PDF、txt、md，PDF 用 pypdf 抽取纯文字。",
    "[8] 落盘位置：data/docs/ 下按 doc_id 分目录，doc_id 随机生成防路径穿越。",
]

SYSTEM = (
    "你是一个严谨的助手。只根据资料回答。"
    "回答时必须在末尾另起一行写：依据：[编号]，并把该条原文完整抄写一遍。"
    "资料里没有的，就只回答「资料里没有」。"
)

MODEL = "qwen3:4b"
OLLAMA_DIR = r"D:\Ollama"
OLLAMA_EXE = os.path.join(OLLAMA_DIR, "ollama.exe")
MODELS_DIR = r"D:\OllamaModels"
BASE_URL = "http://127.0.0.1:11434"


def split_words(text):
    """把一句话切成两字一组的小片段，比如「切分是」切成 切分 / 分是"""
    words = []
    i = 0
    while i < len(text) - 1:
        words.append(text[i:i + 2])
        i = i + 1
    return words


def retrieve(question, lines, top_k=2):
    """算一算每条资料跟问题有多相关，返回最相关的 top_k 条"""
    words = split_words(question)
    scored = []
    for line in lines:
        hit = 0
        for w in words:
            if w in line:
                hit = hit + 1
        scored.append((hit, line))
    scored.sort(reverse=True)
    picked = []
    for hit, line in scored[:top_k]:
        picked.append(line)
    return scored, picked


def server_alive():
    try:
        r = requests.get(BASE_URL + "/api/tags", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def start_server():
    env = dict(os.environ)
    env["OLLAMA_MODELS"] = MODELS_DIR
    return subprocess.Popen(
        [OLLAMA_EXE, "serve"],
        cwd=OLLAMA_DIR,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def ask(doc_text, question):
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": "资料如下：\n" + doc_text + "\n\n问题：" + question},
        ],
        "stream": False,
    }
    try:
        resp = requests.post(BASE_URL + "/api/chat", json=payload, timeout=300)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.ConnectionError:
        print("  [失败] 连不上模型服务，地址是 " + BASE_URL)
        return "（这次调用失败了：连不上服务）", 0, 0.0
    except requests.exceptions.Timeout:
        print("  [失败] 300 秒内没有收到回应")
        return "（这次调用失败了：超时）", 0, 0.0
    except requests.exceptions.HTTPError as e:
        print("  [失败] 服务返回了错误状态码 " + str(e.response.status_code))
        return "（这次调用失败了：服务报错）", 0, 0.0
    return (
        data["message"]["content"],
        data.get("eval_count"),
        round(data.get("total_duration", 0) / 1e9, 2),
    )


def main():
    print("=" * 60)
    print("S3：让程序自己挑出相关的资料")
    print("=" * 60)

    print("\n问题 = " + QUESTION)
    print("资料一共 " + str(len(LINES)) + " 条，只挑最相关的 2 条\n")

    scored, picked = retrieve(QUESTION, LINES, top_k=2)

    print("每条资料的得分（命中了几个问题片段）：")
    for hit, line in scored:
        mark = "  ← 选中" if line in picked else ""
        print("  " + str(hit) + " 分  " + line[:34] + mark)

    print("\n挑出来的是：")
    for line in picked:
        print("  " + line)

    proc = None
    if server_alive():
        print("\n服务已在运行")
    else:
        print("\n服务没在跑，正在启动...")
        proc = start_server()
        for _ in range(60):
            if server_alive():
                print("服务就绪")
                break
            time.sleep(1)
        else:
            print("启动失败")
            sys.exit(1)

    print("\n" + "#" * 16 + " 只把挑中的塞进请求 " + "#" * 16)
    a, t, d = ask("\n".join(picked), QUESTION)
    print("回答 =")
    print(a)
    print(f"（输出 token {t} / 服务端总计 {d} 秒）")
    b, t2, d2 = ask("[7] 解析支持三种格式：PDF、txt、md，PDF 用 pypdf 抽取纯文字。", "解析支持哪些格式？")
    print(f"\n第二次调用的回答 = {b}")

    if proc:
        proc.terminate()
        print("\n已关闭本次启动的服务")


if __name__ == "__main__":
    main()
