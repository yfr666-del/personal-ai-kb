"""03 章 · 错误对照：三种最常见的用法错误，和修正后的写法。

⚠️ 这是执行层（WorkBuddy）临时写的练习文件，**不是 Codex 讲义原文**。
Python 3.13，只用标准库，不联网、不修改主项目。
运行：python learning/functions_contrast.py

错误示范有意保留。每条都配断言：断言没报错，就说明预测成立。
"""


def make_title(name, version):
    """正确版本：接收两个参数，用 return 把拼好的字符串交回去。"""
    return f"{name} v{version}"


# ===== 误用 1：函数里只 print，没有 return =====
def make_title_no_return(name, version):
    print(f"{name} v{version}")


got = make_title_no_return("personal-ai-kb", "0.2.0")
# 屏幕上确实显示了内容，但调用方手里的值是 None
assert got is None
print("误用1：看不到 return，调用方拿到的是 ——", got)


# ===== 误用 2：实参顺序写反 =====
correct = make_title("personal-ai-kb", "0.2.0")
swapped = make_title("0.2.0", "personal-ai-kb")
assert correct == "personal-ai-kb v0.2.0"
assert swapped == "0.2.0 vpersonal-ai-kb"
assert swapped != correct
print("误用2：顺序写反得到 ——", swapped, "（不等于正确写法）")


# ===== 误用 3：少传一个必需参数 =====
# 这一条不是"结果不对"，而是"根本没进函数" —— 调用时就会报错。
try:
    make_title("personal-ai-kb")
except TypeError as e:
    print("误用3：少传参数时报的错 ——", e)

print()
print("修正写法得到：", make_title("personal-ai-kb", "0.2.0"))
