"""Pydantic 入门实验。

用法：python learn_pydantic.py

建议：每个实验先猜结果，再看输出 —— 猜错的那些才是今天真正的收获。
"""

from pydantic import BaseModel, Field


class Doc(BaseModel):
    name: str = Field(min_length=1)
    size_kb: int = Field(gt=0, le=51200)


def try_it(desc: str, fn) -> None:
    print(f"\n{'=' * 56}\n{desc}\n{'-' * 56}")
    try:
        print("结果：", fn())
    except Exception as e:
        print(f"报错类型：{type(e).__name__}")
        print(e)


print("实验 1：传正常数据")
print(Doc(name="test.pdf", size_kb=120))

try_it("实验 2：size_kb 传字符串 '120' —— 会报错吗？",
       lambda: Doc(name="a.pdf", size_kb="120"))

try_it("实验 3：size_kb 传小数 120.7 —— 会报错吗？",
       lambda: Doc(name="a.pdf", size_kb=120.7))

try_it("实验 4：少传 size_kb",
       lambda: Doc(name="a.pdf"))

try_it("实验 5：两个字段都非法，看 Pydantic 怎么报告错误",
       lambda: Doc(name="", size_kb=-5))
