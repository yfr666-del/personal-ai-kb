# -*- coding: utf-8 -*-
"""课程示例 02：把多条资料拼成一段可检查的文本。

来源：学习网站《别把括号当噪音》完整程序。
独立运行，不联网、不修改项目。

这一份跟项目里的 _build_prompt 干的是同一件事，区别只有一处：
这里每条候选是**字典**，所以写 chunk["text"]；
项目里每条候选是**对象**，所以写 c.text。

    运行（项目根目录）：
        .venv\\Scripts\\python.exe learning\\02_data.py
"""

question = "现在支持原神了吗？"
chunks = [
    {"source": "guide.md#0", "text": "现在支持PDF和TXT。"},
    {"source": "guide.md#1", "text": "原神已经实施完成。"},
    {"source": "guide.md#2", "text": "杨斐然是个大帅哥。"},
]

lines = ["参考资料："]
for chunk in chunks:
    source = chunk["source"]
    text = chunk["text"]
    lines.append(f"[{source}] {text}")
lines.append(f"问题：{question}")
prompt = "\n".join(lines)
print(prompt)
