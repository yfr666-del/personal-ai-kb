# -*- coding: utf-8 -*-
r"""
S2 第一课：把资料一起发给模型

它干什么：
    同一个问题，问两次。
    第一次不给资料，第二次把资料塞进去。
    看两次的回答有什么不一样。

怎么用（在项目根目录执行）：
    .venv\Scripts\python.exe learning\s2_context.py

想改问题：
    只改下面 QUESTION 那一行引号里的字。
"""

import os
import subprocess
import sys
import time

import requests

# ============================================================ 你要改的地方
QUESTION = "我的目标是什么？"
# ============================================================

# 资料（摘自你自己项目的 README.md，是真的，不是编的）
DOC = """【项目笔记：personal-ai-kb】
项目名称：personal-ai-kb（个人 AI 知识库系统）
当前状态：M1 骨架 v0.1（tag v0.1.0）
已打通：「收资料」全链路 —— 上传 → 解析 → 切分 → 落盘，有 62 个测试守着。
技术栈：Python 3.13、Pydantic v2、FastAPI、Uvicorn、pypdf、Streamlit、pytest
下一步（未完成）：M2 RAG 最简闭环 + 20 题评估集
我的目标：2027 年 8 月前拿到日薪 350 元以上的技术实习。
"""

SYSTEM = "你是一个严谨的助手，只根据给你的资料回答。资料里没有的，就说「资料里没有」。"

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


def ask(messages):
    """发一次请求，返回（回答, 输出token, 服务端总计秒）"""
    payload = {"model": MODEL, "messages": messages, "stream": False}
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
    print("S2 第一课：把资料一起发给模型")
    print("=" * 60)

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

    # ---------------- 情况 1：不给资料 ----------------
    print("\n" + "#" * 16 + " 情况 1：只问，不给资料 " + "#" * 16)
    print("问题 = " + QUESTION)
    msgs1 = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": QUESTION},
    ]
    a1, t1, d1 = ask(msgs1)
    print("回答 = " + a1)
    print("（输出 token " + str(t1) + " / 服务端总计 " + str(d1) + " 秒）")

    # ---------------- 情况 2：把资料塞进去 ----------------
    print("\n" + "#" * 16 + " 情况 2：把资料一起发过去 " + "#" * 16)
    print("资料 =")
    print(DOC)
    print("问题 = " + QUESTION)
    msgs2 = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": "资料如下：\n" + DOC + "\n\n问题：" + QUESTION},
    ]
    a2, t2, d2 = ask(msgs2)
    print("回答 = " + a2)
    print("（输出 token " + str(t2) + " / 服务端总计 " + str(d2) + " 秒）")

    # ---------------- 对比 ----------------
    print("\n" + "=" * 60)
    print("两次回答一样吗：" + ("一样" if a1.strip() == a2.strip() else "不一样"))
    print("=" * 60)

    if proc:
        proc.terminate()
        print("\n已关闭本次启动的服务")


if __name__ == "__main__":
    main()
