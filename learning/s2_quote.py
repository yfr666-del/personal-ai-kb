# -*- coding: utf-8 -*-
r"""
S2 第二课：让模型说出「依据哪一条」

它干什么：
    把资料切成带编号的几条，要求模型回答时必须标出依据的编号，
    并把那一条原文抄一遍。这样你一眼就能验证它是不是在蒙。

    另外再问一个资料里根本没有的问题，看它会不会硬编一个编号出来。

怎么用（在项目根目录执行）：
    .venv\Scripts\python.exe learning\s2_quote.py

想改问题：
    只改下面 QUESTIONS 里引号里的字。
"""

import os
import subprocess
import sys
import time

import requests

# ============================================================ 你要改的地方
QUESTIONS = [
    "我的项目现在做到哪一步了？",  # 资料里有 → 应该能答，并且给出依据
    "我的项目用了哪些技术？另外我的显卡型号是什么？",  # 一半有依据、一半没依据
]
# ============================================================

# 资料：切成一条一条，每条一个编号（后面 RAG 里的「切分」就是在干这件事）
DOC = """【资料：personal-ai-kb 项目笔记】
[1] 项目名称是 personal-ai-kb（个人 AI 知识库系统）。
[2] 当前状态：M1 骨架 v0.1（tag v0.1.0），已打通「收资料」全链路：上传 → 解析 → 切分 → 落盘，有 62 个测试守着。
[3] 技术栈：Python 3.13、Pydantic v2、FastAPI、Uvicorn、pypdf、Streamlit、pytest。
[4] 下一步（未完成）：M2 RAG 最简闭环 + 20 题评估集。
[5] 我的目标：2027 年 8 月前拿到日薪 325 元以上的技术实习。
"""

SYSTEM = (
    "你是一个严谨的助手。只根据资料回答。"
    "回答时必须在末尾另起一行写：依据：[编号]，"
    "并把该条原文完整抄写一遍——必须包含该条开头的 [编号] 和结尾的句号，"
    "一个字、一个标点都不能少，也不许改写。"
    "资料里没有的，就只回答「资料里没有」，不许编编号，也不许用自己的知识补充。"
)

MODEL = "qwen3:4b"
OLLAMA_DIR = r"D:\Ollama"
OLLAMA_EXE = os.path.join(OLLAMA_DIR, "ollama.exe")
MODELS_DIR = r"D:\OllamaModels"
BASE_URL = "http://127.0.0.1:11434"


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


def ask(user_text):
    """发一次请求，返回（回答, 输出token, 服务端总计秒）"""
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": "资料如下：\n" + DOC + "\n\n问题：" + user_text},
        ],
        "stream": False,
    }
    resp = requests.post(BASE_URL + "/api/chat", json=payload, timeout=300)
    resp.raise_for_status()
    data = resp.json()
    return (
        data["message"]["content"],
        data.get("eval_count"),
        round(data.get("total_duration", 0) / 1e9, 2),
    )


def main():
    print("=" * 60)
    print("S2 第二课：让模型说出「依据哪一条」")
    print("=" * 60)
    print("\n资料 =")
    print(DOC)

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

    for i, q in enumerate(QUESTIONS, 1):
        print("\n" + "#" * 16 + " 问题 " + str(i) + " " + "#" * 16)
        print("问题 = " + q)
        a, t, d = ask(q)
        print("回答 =")
        print(a)
        print("（输出 token " + str(t) + " / 服务端总计 " + str(d) + " 秒）")

    print("\n" + "=" * 60)
    print("看完了：能答的那题，它给的编号对不对？不能答的那题，它有没有编编号？")
    print("=" * 60)

    if proc:
        proc.terminate()
        print("\n已关闭本次启动的服务")


if __name__ == "__main__":
    main()
