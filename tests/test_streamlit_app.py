"""Streamlit 演示页的测试。

Streamlit 自带一个测试工具 AppTest，能把页面脚本在内存里跑一遍，
然后像查 DOM 一样检查渲染结果。有它就不用"改完页面靠手点"了。
"""

import pathlib

import pytest
from streamlit.testing.v1 import AppTest

from app.services import storage

APP = pathlib.Path(__file__).resolve().parents[1] / "streamlit_app.py"


@pytest.fixture(autouse=True)
def 隔离的data目录(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    return tmp_path


def 跑页面():
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.run()
    return at


def 找个指标(app, 名字):
    for m in app.metric:
        if m.label == 名字:
            return m.value
    return None


# 造一段够长的文字，短了切不开 —— 而且 chunk_size 滑块最小值是 50，
# 数据太短的话不管怎么拖都只有 1 块，测不出东西
_长文本 = "".join(f"第{i}句话，讲的是切分策略。" for i in range(30))


def 造一份文档():
    """往隔离目录里塞一份文档，让页面有东西可展示。"""
    storage.save_chunks(
        "aaa111",
        {
            "doc_id": "aaa111",
            "filename": "测试笔记.md",
            "content_type": "text/markdown",
            "size_kb": 1,
            "uploaded_at": "2026-10-14T21:00:00",
            "text": _长文本,
            "text_length": len(_长文本),
            "chunk_count": 1,
            "chunks": [_长文本],
        },
    )


def test_空文档库时页面也能正常打开():
    at = 跑页面()
    assert at.exception == []
    assert [t.value for t in at.title] == ["个人 AI 知识库"]
    assert [t.label for t in at.tabs] == ["上传文档", "文档库", "看切分效果"]


def test_空文档库时给出提示而不是报错():
    at = 跑页面()
    assert "文档库是空的" in " ".join(i.value for i in at.info)


def test_有文档时统计数字对得上():
    造一份文档()
    at = 跑页面()
    assert at.exception == []
    assert 找个指标(at, "已收文档") == "1 份"
    assert len(at.dataframe[0].value) == 1


def test_拖动滑块能改变块数():
    造一份文档()
    at = 跑页面()

    at.slider[0].set_value(100)  # chunk_size
    at.slider[1].set_value(0)  # chunk_overlap
    at.run()

    assert at.exception == []
    assert 找个指标(at, "切成多少块") != "1 块"  # 切细之后块数必然变多


def test_重叠大于等于块大小时给出错误提示():
    造一份文档()
    at = 跑页面()

    at.slider[0].set_value(100)
    at.slider[1].set_value(150)
    at.run()

    assert at.exception == []  # 不崩，而是好好显示错误
    assert any("重叠必须小于块大小" in e.value for e in at.error)
