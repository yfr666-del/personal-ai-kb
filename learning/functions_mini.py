"""03 章 · 最小示例：一个函数怎么接收值、怎么用、怎么把结果交回来。

⚠️ 这是执行层（WorkBuddy）按 make_title(name, version) 规格临时写的最小练习文件，
   **不是 Codex 讲义原文**。两边若有出入，以学习网站上的为准。

Python 3.13，只用标准库，不联网、不修改主项目。
运行：python learning/functions_mini.py
"""


def make_title(name, version):
    """接收两个形参 name 和 version，返回一个拼好的标题字符串。"""
    return f"{name} v{version}"


# 调用：括号里这两个是实参，会按位置填进上面的形参
result = make_title("personal-ai-kb", "0.2.0")

assert result == "personal-ai-kb v0.2.0"
print(result)
