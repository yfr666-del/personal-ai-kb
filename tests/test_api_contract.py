# -*- coding: utf-8 -*-
"""现有 HTTP 接口的契约测试 —— **不新增 /ask 问答接口**。

## 这次实际验证了什么，必须先说清楚

当前项目虚拟环境**没有装 httpx**，而 FastAPI 的 TestClient 依赖它：

```
RuntimeError: The starlette.testclient module requires the httpx2 package to be installed.
```

所以本文件会被 pytest 整体标记为 **skipped**，
**HTTP 部分明确记为「缺现有依赖，未运行」**。

不做的三件事（避免用别的东西冒充 HTTP 结论）：
  - 不用「直接调用路由函数」来替代 HTTP 状态码结论
  - 不启动 uvicorn、不发外网请求
  - 不在报告里声称 HTTP 已通过

等 httpx 获批安装后，本文件无需改动即可直接参与运行。
"""

from __future__ import annotations

import pytest

from app.models.document import ALLOWED_CONTENT_TYPES, ALLOWED_SUFFIXES
from app.services import storage

try:
    import httpx  # noqa: F401  （TestClient 的底层依赖）
    from fastapi.testclient import TestClient

    _HTTP_AVAILABLE = True
    _SKIP_REASON = ""
except Exception as exc:  # noqa: BLE001  不论缺什么，统一记为不可用
    _HTTP_AVAILABLE = False
    _SKIP_REASON = f"缺 httpx，TestClient 不可用：{type(exc).__name__}"

pytestmark = pytest.mark.skipif(
    not _HTTP_AVAILABLE, reason=_SKIP_REASON or "HTTP 测试依赖不可用"
)


def _make_client(monkeypatch, tmp_path):
    """建一个进程内 TestClient，并把存储目录全程指向临时目录。

    为什么要换 DATA_DIR：否则测试期间的一次写入会污染真实资料库，
    之后「多检索到一个片段」的变化其实来自测试残留，而不是代码改动。
    """
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path / "data")
    from app.main import app

    return TestClient(app)


def test_health_returns_200_and_contract_json(monkeypatch, tmp_path):
    """/health 的既定 JSON 不能被悄悄改掉。"""
    client = _make_client(monkeypatch, tmp_path)

    resp = client.get("/health")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "app": "personal-ai-kb"}


def test_allowed_types_match_model_constants(monkeypatch, tmp_path):
    """接口给出的白名单必须与模型层常量一致，且不依赖列表顺序。"""
    client = _make_client(monkeypatch, tmp_path)

    resp = client.get("/documents/allowed")

    assert resp.status_code == 200
    data = resp.json()
    assert set(data["allowed_extensions"]) == set(ALLOWED_SUFFIXES)
    assert set(data["allowed_content_types"]) == set(ALLOWED_CONTENT_TYPES)


def test_missing_doc_id_returns_404_with_detail(monkeypatch, tmp_path):
    """格式合法但不存在的 doc_id 应为 404 且带 detail。

    这里靠「把 DATA_DIR 指向临时空目录」来保证它不存在，
    不去访问真实资料库来制造这个前提。
    """
    client = _make_client(monkeypatch, tmp_path)

    resp = client.get("/documents/0123456789ab")  # 12 位十六进制，格式合法

    assert resp.status_code == 404
    assert "detail" in resp.json()
