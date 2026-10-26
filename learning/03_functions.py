"""03 章 · 完整程序：把 make_title 的返回值用进一段多行文本。

⚠️ 这是执行层（WorkBuddy）按 make_title(name, version) 规格临时写的练习文件，
   **不是 Codex 讲义原文**。两边若有出入，以学习网站上的为准。

Python 3.13，只用标准库，不联网、不修改主项目。
运行：python learning/03_functions.py

本章三件事在这份文件里分别对应：
  接收 → def 后面的形参
  使用 → 函数体里 f-string 中的 {name} / {version}
  调用 → 下面 title = make_title(...)，返回值被这个变量接住
"""


def make_title(name, version):
    """接收 name 和 version，返回拼好的标题行。"""
    return f"{name} v{version}"


def build_report(name, version, notes):
    """接收三个参数；标题那一行交给 make_title 做，自己只负责组装正文。"""
    lines = [make_title(name, version), ""]
    for item in notes:
        lines.append(f"- {item}")
    return "\n".join(lines)


# ① 单独调用：返回值被 title 接住
title = make_title("personal-ai-kb", "0.2.0")

# ② 再调用另一个函数，它内部又会去调用 make_title
notes = ["来源标识要保留", "资料里没有的答案不编"]
report = build_report("personal-ai-kb", "0.2.0", notes)

print(report)
print()
print("单独取标题：", title)

# ---- 学员动手区：只改下面这一处 ----
# 把版本号从 "0.2.0" 换成你自己想写的，先猜输出会变成什么样再跑。
mine = make_title("personal-ai-kb", "0.3.0")
print("改过版本号后：", mine)
