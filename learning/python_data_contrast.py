# -*- coding: utf-8 -*-
"""课程示例 03：错误写法与修正写法的对照。

遍历字典默认拿到的是**键**，不是正文；要取正文必须用键名下标。

    运行（项目根目录）：
        .venv\\Scripts\\python.exe learning\\python_data_contrast.py
"""

chunks = [{"text": "PDF", "source": "g#0"}, {"text": "TXT", "source": "g#1"}]

wrong = list(chunks[0])
fixed = chunks[0]["text"]
assert wrong == ['text', 'source']
assert fixed == 'PDF'
assert wrong != fixed
print("错误写法得到：", wrong)
print("修正写法得到：", fixed)
