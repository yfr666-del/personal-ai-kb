# -*- coding: utf-8 -*-
"""课程示例 01：先取一条记录，再取字段。

来源：学习网站《别把括号当噪音：Python数据到底长什么样？》最小示例。
Python 3.13 标准库，独立运行，不联网、不修改项目。

    运行（项目根目录）：
        .venv\\Scripts\\python.exe learning\\python_data_mini.py
"""

chunks = [{"text": "PDF", "source": "g#0"}, {"text": "TXT", "source": "g#1"}]

result = chunks[0]["text"]
assert result == 'PDF'
print(result)
