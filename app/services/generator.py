# -*- coding: utf-8 -*-
"""聊天模型调用：把「一段话」交给 qwen3:4b，拿回「一段话」。

跟 embedder.py 一样，这里也只做一件事，并且**只认 llm_model 一个模型名**。
分开放的原因：上一轮实测过，拿聊天模型去请求 /api/embed 会返回 501
（仅限当前这个 qwen3:4b 与当前这个 Ollama 接口版本，不代表其它模型）。

这一层**不做任何"有没有答案"的判断**：
它只是把收到的文字发出去、把回话带回来。资料够不够、回答对不对，
那是调用方的事 —— 本组件不保证模型会拒答，也不保证它答得对。
"""

from __future__ import annotations

import requests

from app.core.config import settings

# 与 embedder 同样的理由：本地地址不走系统代理，
# 否则"服务没起"会被代理伪装成 502，排查方向直接跑偏。
_local_session = requests.Session()
_local_session.trust_env = False


class GenerationError(Exception):
    """生成回答这一步失败了。message 是能直接给人看的话。"""


class GenerationUnavailableError(GenerationError):
    """连不上本地模型服务（服务没起 / 地址不对）。"""


def generate(prompt_text: str, system_text: str | None = None) -> tuple[str, int | None, float]:
    """把一整段话交给聊天模型，返回 (回答文字, 输出 token 数, 服务端耗时秒)。

    输出 token 数与耗时可能为 None / 0.0 —— 服务端没给这个字段时就这样，
    调用方不要把它们当成"质量指标"，它们只是顺手带回来的观察值。
    """
    if not prompt_text or not prompt_text.strip():
        raise ValueError("要发给模型的内容是空的")

    messages = []
    if system_text:
        messages.append({"role": "system", "content": system_text})
    messages.append({"role": "user", "content": prompt_text})

    url = settings.ollama_base_url.rstrip("/") + "/api/chat"
    payload = {
        "model": settings.llm_model,
        "messages": messages,
        "stream": False,
    }

    try:
        resp = _local_session.post(url, json=payload, timeout=300)
        resp.raise_for_status()
    except requests.exceptions.ConnectionError as e:
        raise GenerationUnavailableError(f"连不上本地模型服务：{url}") from e
    except requests.exceptions.Timeout as e:
        raise GenerationError("请求超时（300 秒）") from e
    except requests.exceptions.HTTPError as e:
        code = e.response.status_code if e.response is not None else "未知"
        raise GenerationError(f"模型服务返回错误状态码 {code}") from e

    try:
        data = resp.json()
    except ValueError as e:
        raise GenerationError("模型服务返回的不是合法 JSON") from e

    if not isinstance(data, dict):
        raise GenerationError("模型服务返回的不是一个 JSON 对象")

    # data["message"]["content"] 是直接下标取值：
    # 这个字段是 /api/chat 的核心字段，缺了就没法干活，宁可报错也不要静默返回空串。
    message = data.get("message")
    if not isinstance(message, dict) or "content" not in message:
        raise GenerationError("返回里没有 message.content")

    content = message["content"]
    if not isinstance(content, str):
        raise GenerationError("返回里的 content 不是字符串")

    tokens = data.get("eval_count")
    duration_ns = data.get("total_duration")
    seconds = round(duration_ns / 1e9, 2) if isinstance(duration_ns, (int, float)) else 0.0

    return content, tokens if isinstance(tokens, int) else None, seconds
