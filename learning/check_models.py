"""DocumentMeta 模型自检 —— 验证校验规则真的生效。

用法：python learning/check_models.py
"""

import sys
from pathlib import Path

# 脚本搬进 learning/ 之后，父目录（项目根）就不在模块搜索路径里了，
# 会导致 `import app` 失败。这两行把项目根加回去。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic import ValidationError

from app.models.document import DocumentMeta


def show(title: str, fn) -> None:
    print(f"\n{'-' * 60}\n{title}")
    try:
        print("通过：", fn())
    except ValidationError as e:
        print("被拦截：")
        for err in e.errors():
            field = ".".join(str(x) for x in err["loc"])
            print(f"   - 字段 {field}：{err['msg']}")


show(
    "1. 一份合法文档（其他字段走默认值）",
    lambda: DocumentMeta(
        doc_id="d001", filename="paper.pdf",
        content_type="application/pdf", size_kb=800,
    ),
)

show(
    "2. 文件名想偷渡路径：../../etc/passwd",
    lambda: DocumentMeta(
        doc_id="d002", filename="../../etc/passwd",
        content_type="text/plain", size_kb=1,
    ),
)

show(
    "3. 后缀不在白名单：a.exe",
    lambda: DocumentMeta(
        doc_id="d003", filename="a.exe",
        content_type="text/plain", size_kb=1,
    ),
)

show(
    "4. content_type 不是三选一",
    lambda: DocumentMeta(
        doc_id="d004", filename="a.pdf",
        content_type="application/zip", size_kb=1,
    ),
)

show(
    "5. 跨字段校验：overlap >= chunk_size",
    lambda: DocumentMeta(
        doc_id="d005", filename="a.pdf", content_type="application/pdf",
        size_kb=1, chunk_config={"chunk_size": 100, "chunk_overlap": 100},
    ),
)

show(
    "6. 字符串自动转换 + 标签自动清洗去重",
    lambda: DocumentMeta(
        doc_id="d006", filename="A.PDF", content_type="application/pdf",
        size_kb="800", tags=[" rag ", "rag", "", "  ", "检索"],
    ),
)
