r"""
S1 第二课：消息格式 messages
==================================================================
【它能帮你干什么】
    让你亲眼看到一件事：
    你问模型"一句话"，电脑真正发出去的不是这句话，
    而是"一整组带标签的对话记录"，这个东西叫 messages。

【为什么现在要学】
    上一课 s1_hello_model.py 里，假模型接收的是 {"question": "..."}
    —— 那是我随手定的格式，真实世界没有任何一家模型认它。
    换成真模型，那一行就得整个改掉。

    而 messages 是行业标准格式：
        OpenAI 先这么定的，后来通义、智谱、Ollama 几乎全都跟了。
    学会它，换哪家只改网址，不用改数据结构。

【这节课只学一个知识点】
    messages = 一组带标签的对话记录
    每条消息两个字段：
        role    = 谁说的
        content = 说了什么

【三个 role 要记住】
    system    → 你写的，但不是提问，是"给模型定规矩"
    user      → 你写的，真正的提问
    assistant → 模型自己上一轮说过的话（多轮对话时才出现）

【现在可以完全无视的】
    - 温度 / top_p / 流式输出 / token 计费
    - 多模态、函数调用

【怎么运行】
    1. Win 键 → 输入 powershell → 回车
    2. 复制粘贴下面这行，回车：

    cd C:\Users\21511\Desktop\personal-ai-kb; .venv\Scripts\python.exe learning\s1_messages.py
==================================================================
"""

import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

# Windows 中文系统默认 GBK，强制 utf-8 打印避免中文乱码
sys.stdout.reconfigure(encoding="utf-8")

import requests

PORT = 8124


class FakeModelHandler(BaseHTTPRequestHandler):
    """假模型：如实回显它收到的每一条消息，不假装自己会思考。"""

    def do_POST(self):
        # 1. 看包裹多大 → 2. 读出字节 → 3. 解码 → 4. 解析成字典
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        data = json.loads(raw.decode("utf-8"))

        # 5. 取出 messages（注意：是一组，不是一个）
        messages = data.get("messages", [])

        # 6. 如实回显，让学员看清"发出去的到底是什么"
        lines = [f"我收到了 {len(messages)} 条消息："]
        for i, m in enumerate(messages, 1):
            lines.append(f"  第{i}条 [{m.get('role')}] {m.get('content')}")

        answer = "\n".join(lines)

        # 7. 打包寄回
        body = json.dumps({"answer": answer}, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass  # 关掉默认英文日志


def start_fake_model():
    """把假模型服务跑起来（后台线程）。"""
    server = HTTPServer(("127.0.0.1", PORT), FakeModelHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server


def send(messages):
    """
    把一整组 messages 发给模型，打印全过程。

    参数 messages：一组字典，每个字典形如
        {"role": "user", "content": "你想问的话"}
    """
    payload = {"messages": messages}

    print("\n【messages 长这样】")
    print(json.dumps(messages, ensure_ascii=False, indent=2))

    print("\n【真正发出去的字节】")
    print(json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    # 关键一行：requests 默认会读系统 http_proxy 环境变量，
    # 不关掉的话访问 127.0.0.1 也会被送去代理，拿到假的 502
    session = requests.Session()
    session.trust_env = False

    resp = session.post(f"http://127.0.0.1:{PORT}/chat", json=payload, timeout=10)

    print(f"\n【状态码】{resp.status_code}")
    print("【模型回显】")
    print(resp.json()["answer"])


def main():
    print("=" * 60)
    print("S1 第二课：消息格式 messages")
    print("（模型是假的，但发出去的数据形状是真的）")
    print("=" * 60)

    server = start_fake_model()
    time.sleep(0.3)

    print("\n\n################ 情况 1：只问一句话 ################")
    send([
        {"role": "user", "content": "什么是 共产主义？"},
    ])

    print("\n\n################ 情况 2：先定规矩，再问 ################")
    send([
        {"role": "system", "content": "你是一个严谨的助手，只根据给定资料回答。"},
        {"role": "user", "content": "什么是 共产主义？"},
    ])

    print("\n\n################ 情况 3：接着上一轮追问 ################")
    send([
        {"role": "system", "content": "你是一个严谨的助手，只根据给定资料回答。"},
        {"role": "user", "content": "什么是 共产主义？"},
        {"role": "assistant", "content": "共产主义是一种社会制度，其目标是实现无阶级、无国家的社会。"},
        {"role": "user", "content": "那它和资本主义有什么区别？"},
    ])

    server.shutdown()

    print("\n\n" + "=" * 60)
    print("跑完了。假模型服务已关闭。")
    print("=" * 60)
    print()
    print("重点：情况 3 里有 assistant —— 那不是模型记住的，")
    print("      是你把上一轮的对话记录一起重发了一遍。")
    print("      模型没有记忆。对话越长，重发的东西越多。")


if __name__ == "__main__":
    main()
