# -*- coding: utf-8 -*-
r"""
S1 台阶①收尾：真实模型调用（不是模拟）

它干什么：
    真的启动本地 Ollama 服务，真的把问题发给真实的 qwen3:4b 模型，
    真的打印模型返回的回答。这跟前面几个假模型脚本不一样。

怎么用（在项目根目录执行）：
    .venv\Scripts\python.exe learning\s1_real_call.py

想改问题：
    只改下面 QUESTION 那一行引号里的字，其他别动。改完 Ctrl+S。
"""

import json
import os
import subprocess
import sys
import time

import requests

# ============================================================ 你要改的地方
QUESTION = "我是计算机专业大二的学生，想做ai应用方向，现在最应该做什么"
SYSTEM = "你是一个简洁的助手，请列四条建议。"
MODEL = "qwen3:4b"
# ============================================================

OLLAMA_DIR = r"D:\Ollama"
OLLAMA_EXE = os.path.join(OLLAMA_DIR, "ollama.exe")
MODELS_DIR = r"D:\OllamaModels"
BASE_URL = "http://127.0.0.1:11434"


def server_alive():
    """服务是不是已经在跑了"""
    try:
        r = requests.get(BASE_URL + "/api/tags", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def start_server():
    """启动 ollama serve，返回进程对象"""
    env = dict(os.environ)
    env["OLLAMA_MODELS"] = MODELS_DIR
    return subprocess.Popen(
        [OLLAMA_EXE, "serve"],
        cwd=OLLAMA_DIR,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main():
    print("=" * 60)
    print("S1 台阶①：真实模型调用")
    print("模型 = " + MODEL + "（本地 Ollama，不是模拟）")
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

    # ---------------- 第 1 步：输入 ----------------
    print("\n" + "#" * 18 + " 第 1 步：输入 " + "#" * 18)
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": QUESTION},
    ]
    payload = {"model": MODEL, "messages": messages, "stream": False}
    print("messages =")
    print(json.dumps(messages, ensure_ascii=False, indent=2))

    # ---------------- 第 2 步：请求 ----------------
    print("\n" + "#" * 18 + " 第 2 步：请求 " + "#" * 18)
    print("POST " + BASE_URL + "/api/chat")
    print("（首次调用要把 2.5GB 模型加载进显存，慢是正常的）")

    t0 = time.time()
    resp = requests.post(BASE_URL + "/api/chat", json=payload, timeout=300)
    resp.raise_for_status()
    elapsed = time.time() - t0

    # ---------------- 第 3 步：输出 ----------------
    print("\n" + "#" * 18 + " 第 3 步：输出 " + "#" * 18)
    print("HTTP 状态码 = " + str(resp.status_code))
    print()
    print("原始响应文本（前 600 字符）:")
    print(resp.text[:600])
    print()

    data = resp.json()
    print("-" * 60)
    print("模型      = " + str(data.get("model")))
    print("回答要求  = " + SYSTEM)
    print()
    print("回答      = " + data["message"]["content"])
    print()
    print("墙钟耗时  = " + str(round(elapsed, 2)) + " 秒（含首次加载模型）")
    print("-" * 60)
    print("统计字段（单位已换算）:")
    print("  输入token  prompt_eval_count = " + str(data.get("prompt_eval_count")))
    print("  输出token  eval_count        = " + str(data.get("eval_count")))
    print("  加载模型   load_duration    = " + str(round(data.get("load_duration", 0) / 1e9, 2)) + " 秒")
    print("  处理输入   prompt_eval_dur  = " + str(round(data.get("prompt_eval_duration", 0) / 1e9, 2)) + " 秒")
    print("  生成输出   eval_duration    = " + str(round(data.get("eval_duration", 0) / 1e9, 2)) + " 秒")
    print("  服务端总计 total_duration   = " + str(round(data.get("total_duration", 0) / 1e9, 2)) + " 秒")
    eval_dur = data.get("eval_duration", 0) / 1e9
    if eval_dur > 0:
        print("  生成速度   = " + str(round(data.get("eval_count", 0) / eval_dur, 1)) + " token/s（仅生成阶段）")
    print("-" * 60)

    if proc:
        proc.terminate()
        print("\n已关闭本次启动的服务")


if __name__ == "__main__":
    main()
