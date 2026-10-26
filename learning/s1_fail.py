r"""
S1 第四课：调用会怎么失败，以及怎么兜住
==================================================================
【它能帮你干什么】
    让你亲眼看到：一次模型调用失败的四种样子。
    这四种报错是真实的 —— 不是我编的措辞，是 Python 真的抛出来的。

【为什么先学这个，跳过台阶③】
    台阶③是"改提示词看回答变化"，那必须靠真模型。
    假模型只会回显，换一百种说法回显都一样，演不出来。
    台阶④现在就能真跑，因为报错是真的。

【这节课只学一个知识点】
    一次调用有四种典型失败：
        1. 连不上   → ConnectionError   （服务没开 / 端口写错）
        2. 超时     → Timeout           （服务开了但太慢）
        3. 网址错   → HTTPError 404     （路径写错）
        4. 内容坏   → ValueError        （返回的不是合法 JSON）

    兜住的办法：try / except

【现在可以完全无视的】
    - 重试策略、熔断、异步、日志框架
    - 真正的 API Key 长什么样

【怎么运行】
    1. Win 键 → 输入 powershell → 回车
    2. 复制粘贴下面这行，回车：

    cd C:\Users\21511\Desktop\personal-ai-kb; .venv\Scripts\python.exe learning\s1_fail.py
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

PORT = 8125


class FakeModelHandler(BaseHTTPRequestHandler):
    """假模型，带一个故意磨蹭的 /slow 路径，用来演示超时。"""

    def do_POST(self):
        # 先认门牌号：只认 /chat 和 /slow，其他一律 404
        # （真实服务也是这样：路径写错就 404，不会随便回你一个 200）
        if self.path not in ("/chat", "/slow"):
            body = b"404 not found: wrong path"
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        data = json.loads(raw.decode("utf-8"))
        messages = data.get("messages", [])
        last = messages[-1]["content"] if messages else ""

        # 故意磨蹭 5 秒，配合客户端 timeout=1 制造真实超时
        if self.path == "/slow":
            time.sleep(5)

        answer = f"【假模型】你说的是：{last}"
        body = json.dumps({"answer": answer}, ensure_ascii=False).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()

        # 客户端一旦超时就会先断开，这时候再写就会抛异常。
        # 这不是 bug，是超时场景的正常现象，吞掉即可。
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            pass

    def log_message(self, *args):
        pass  # 关掉默认英文日志


def start_fake_model():
    """把假模型服务跑起来（后台线程）。"""
    server = HTTPServer(("127.0.0.1", PORT), FakeModelHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server


def ask(session, url, question, timeout):
    """
    发一次调用，把可能出的错兜住，返回一句人话。

    参数：
        session  : requests 的会话对象
        url      : 模型服务网址
        question : 你想问的话
        timeout  : 最多等多少秒（超时就放弃）
    """
    messages = [{"role": "user", "content": question}]

    try:
        resp = session.post(url, json={"messages": messages}, timeout=timeout)

        # raise_for_status()：状态码不是 2xx 就主动抛异常
        resp.raise_for_status()

        return f"成功（{resp.status_code}）：{resp.json()['answer']}"

    except requests.exceptions.ConnectionError:
        return "失败：连不上模型服务 —— 服务没开，或网址/端口写错了"

    except requests.exceptions.Timeout:
        return f"失败：超时 —— 服务开了，但超过 {timeout} 秒还没回"

    except requests.exceptions.HTTPError:
        return f"失败：服务返回错误状态码（{resp.status_code}）—— 网址路径写错了？"

    except (ValueError, OSError):
        return "失败：响应内容不是合法 JSON —— 服务返回了别的东西"


def main():
    print("=" * 62)
    print("S1 第四课：调用会怎么失败")
    print("（模型是假的，但下面这些报错是 Python 真的抛出来的）")
    print("=" * 62)

    server = start_fake_model()
    time.sleep(0.3)

    base = f"http://127.0.0.1:{PORT}"

    # 关键：trust_env = False，不让 requests 去读系统代理，
    # 否则访问 127.0.0.1 也会被送去代理，拿到假的 502
    session = requests.Session()
    session.trust_env = False

    print("\n\n############ 情况 1：正常调用 ############")
    print("   " + ask(session, base + "/chat", "什么是 RAG？", timeout=0.001))

    print("\n\n############ 情况 2：服务关掉后再调 ############")
    server.shutdown()
    server.server_close()
    time.sleep(0.3)
    print("   " + ask(session, base + "/chat", "服务还活着吗？", timeout=3))

    print("\n\n############ 情况 3：网址路径写错 ############")
    server2 = start_fake_model()
    time.sleep(0.3)
    print("   " + ask(session, base + "/chat2222", "有人在吗？", timeout=3))

    print("\n\n############ 情况 4：服务磨蹭（超时）############")
    print("   " + ask(session, base + "/slow", "慢慢想，不着急", timeout=1))

    print("\n\n############ 情况 5：端口写错（重点看这个）############")
    print("   服务端开在 8125，这里故意写成 9999：")
    print("   " + ask(session, base + "chat", "有人在吗？", timeout=3))

    server2.shutdown()
    server2.server_close()

    print("\n\n" + "=" * 62)
    print("跑完了。")
    print("=" * 62)
    print()
    print("四种失败对应四种处理，不要一上来就 except Exception：")
    print("  ConnectionError → 检查服务开了没、端口对不对")
    print("  Timeout         → 要么等久点，要么换个更小的模型")
    print("  HTTPError       → 检查网址路径，或 Key 是不是错了（401/403）")
    print("  ValueError      → 服务返回的不是 JSON，看看它到底回了啥")


if __name__ == "__main__":
    main()
