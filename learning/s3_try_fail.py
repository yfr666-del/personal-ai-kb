# -*- coding: utf-8 -*-
r"""
试验场：故意让 ask() 失败一次，看它会怎样

它干什么：
    把服务地址改成一个没人监听的端口，然后照样调用 ask()。
    没有 try/except 时，程序会抛一大段红字，直接崩；
    加了 try/except 之后，它会打印一行 [失败]，然后照常交出三个值。

怎么用（在项目根目录执行）：
    .venv\Scripts\python.exe learning\s3_try_fail.py

你要改的地方：
    下面 BAD_URL 里的端口号，换成任何没人用的数字（59999 / 59888 / 58888）
"""

import os
import sys

# 让 requests 不走系统代理。否则连不上时会被代理接管，报 502 而不是「连不上」
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import s3_retrieve as kb

BAD_URL = "http://127.0.0.1:59999"

kb.BASE_URL = BAD_URL

print("=" * 60)
print("故意调用一个连不上的地址：" + BAD_URL)
print("=" * 60)

answer, tokens, seconds = kb.ask("随便一条资料", "随便一个问题")

print("拿到的回答 = " + answer)
print(f"拿到的 token = {tokens}，耗时 = {seconds}")
print("程序还活着 —— 这行能打出来，就说明它没崩")
