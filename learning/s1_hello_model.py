# -*- coding: utf-8 -*-
r"""
S1 第一课：最小的模型调用（学习用）
==================================================================
【它能帮你干什么】
    让你亲眼看到"调用一次模型"到底发生了什么。
    不是文字描述，是真的把一个字典发出去、真的收到一个字典、
    真的把每一步的内容打印出来。

【为什么现在要学这个】
    你的项目（个人 AI 知识库）最终要干的事是：
        "你问一句话
          → 系统去资料里找相关段落
          → 把找到的内容 + 你的问题一起交给模型
          → 模型回答，并说明它依据了哪一段"
    其中最核心的一环就是"把东西交给模型、拿回回答"。
    这一步不跑通，后面的检索、引用、Agent 全是空中楼阁。

【这节课只学一个知识点】
    一次模型调用 = 三样东西：输入（问题）→ 请求（寄出去）→ 输出（回答）

【现在可以完全无视的】
    - 模型是怎么训练出来的
    - temperature / top_p / 流式输出（后面再学）
    - 向量、Embedding、RAG（那是 S3 的事）
    - HTTP 协议的底层细节（现在只要懂"寄快递"就够了）

【怎么运行】
    1. Win 键 → 输入 powershell → 回车
    2. 复制粘贴下面这行，回车：

    cd C:\Users\21511\Desktop\personal-ai-kb; .venv\Scripts\python.exe learning\s1_hello_model.py

【⚠️ 关于"假"的说明】
    这个脚本里的"模型"是假的，是下面 FakeModelHandler 冒充的，
    它只会把你的问题原样包一句回给你。
    真实模型调用目前在这台机器上跑不通（缺库 + Ollama 未安装），
    我不会假装跑通。
    但"发请求 / 收响应"的步骤、数据形状、报错方式，和真的一模一样。
    等真模型就绪，只需要改一个网址，其余代码不用动。
==================================================================
"""

import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

# Windows 中文系统默认编码是 GBK，这里强制 utf-8 打印，避免中文乱码
sys.stdout.reconfigure(encoding="utf-8")

import requests

PORT = 8123


# ==================================================================
# 第一部分：一个假模型服务
# ------------------------------------------------------------------
# 真实情况：模型是"另一个程序"，运行在别的地方（本机另一个进程，或者云端服务器）
# 这里为了让你"只跑一个脚本就能看到全过程"，把它写在同一个文件里
# ==================================================================
class FakeModelHandler(BaseHTTPRequestHandler):
    """假装自己是模型：收到问题，回一句固定格式的话。"""

    def do_POST(self):
        # 1. 看对方寄来的包裹有多大（请求头里写着 Content-Length）
        length = int(self.headers.get("Content-Length", 0))

        # 2. 按这个长度把包裹里的原始字节读出来
        raw = self.rfile.read(length)

        # 3. 字节 → 文字（utf-8 解码）→ 字典（JSON 解析）
        data = json.loads(raw.decode("utf-8"))

        # 4. 取出对方问的问题
        question = data.get("question", "")

        # 5. 拼一句"回答"。这里没有真模型，只是把问题包一下回给你
        answer = f"【假模型】你问的是：{question}"

        # 6. 把回答打包：字典 → JSON 文字 → utf-8 字节
        body = json.dumps({"answer": answer}, ensure_ascii=False).encode("utf-8")

        # 7. 写状态行：200 = 我处理成功了
        self.send_response(200)

        # 8. 写响应头：告诉对方"我寄回去的是 JSON，用 utf-8 编码，长度是多少"
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()

        # 9. 把内容寄出去
        self.wfile.write(body)

    def log_message(self, *args):
        # 关掉默认的英文访问日志，免得干扰看输出
        pass


def start_fake_model():
    """把假模型服务跑起来（放在后台线程，不阻塞主流程）。"""
    server = HTTPServer(("127.0.0.1", PORT), FakeModelHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


# ==================================================================
# 第二部分：真正的"一次模型调用"
# ==================================================================
def call_model(url, question):
    """
    一次模型调用，只有三步。

    参数：
        url      : 模型服务的网址
        question : 你想问的话（字符串）

    返回：
        模型回答的字符串
    """
    # ---------- 第 1 步：输入 ----------
    # 模型不认你的"想法"，只认数据。所以先把问题装进一个字典。
    payload = {"question": question}

    print("\n【第 1 步 输入】把问题装进字典")
    print(f"    question = {question!r}")
    print(f"    payload  = {payload}")
    print(f"    在网络上真实的样子（字节）：")
    print(f"    {json.dumps(payload, ensure_ascii=False).encode('utf-8')}")

    # ---------- 第 2 步：请求 ----------
    print(f"\n【第 2 步 请求】寄出去")
    print(f"    发往 = {url}")
    print(f"    方式 = POST（POST = 寄包裹，GET = 索要一张现成的纸）")

    session = requests.Session()
    # ↓ 这一行是坑点：requests 默认会读系统的 http_proxy 环境变量。
    #   你机器上有代理 127.0.0.1:56494，如果不关掉，
    #   访问 127.0.0.1 的请求也会被送去代理，然后拿到假的 502。
    session.trust_env = False

    response = session.post(url, json=payload, timeout=10)

    print(f"    已寄出，等待回信……")

    # ---------- 第 3 步：输出 ----------
    print(f"\n【第 3 步 输出】收回来")
    print(f"    HTTP 状态码 = {response.status_code}   （200=成功，404=网址错，500=服务崩了）")
    print(f"    原始响应文本 = {response.text}")

    data = response.json()          # 文字 → 字典
    answer = data["answer"]         # 从字典里取 answer 字段

    print(f"    取出 answer  = {answer}")

    return answer


def main():
    print("=" * 62)
    print("S1 第一课：最小的模型调用")
    print("（模型是假的，但「输入 → 请求 → 输出」的形状和真的一模一样）")
    print("=" * 62)

    server = start_fake_model()
    time.sleep(0.3)  # 等服务起来

    url = f"http://127.0.0.1:{PORT}/chat"

    # 调用一次
    call_model(url, "什么是 RAG？")

    # 再调用一次，换个问题 —— 让你看到"输入变了，输出跟着变"
    print("\n" + "-" * 62)
    print("再试一次，换个问题：")
    print("-" * 62)
    call_model(url, "我的项目下一步该做什么？")

    server.shutdown()

    print("\n" + "=" * 62)
    print("跑完了。假模型服务已关闭。")
    print("=" * 62)


if __name__ == "__main__":
    main()
