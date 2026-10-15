"""个人 AI 知识库 —— M1 演示页。

跑法（在项目根目录）：
    .venv/Scripts/python.exe -m streamlit run streamlit_app.py

它干的事：把「上传 -> 解析 -> 切分 -> 落盘」这条链路做成能点的界面。

注意：这是 M1 的"丑页面"，只做了收资料那一段。
真正的问答（检索 + 生成 + 引用）是 M2 的事，这一页现在还不能回答任何问题。

另外说明一下：这个页面是**直接调 Python 函数**的，没走 HTTP 接口。
这么做是为了让你少开一个服务、少踩端口的坑。
等 M4 工程化的时候会改成调 HTTP 接口 —— 那时候前后端要分开部署。
"""

import streamlit as st

from app.models.document import ALLOWED_SUFFIXES, ChunkConfig
from app.services.chunker import split_text
from app.services.ingest import IngestError, ingest_document
from app.services.storage import StorageError, list_documents, load_chunks

st.set_page_config(page_title="个人 AI 知识库", layout="wide")

st.title("个人 AI 知识库")
st.caption("M1 骨架 · 收资料阶段：上传 -> 解析 -> 切分 -> 落盘")

docs = list_documents()

with st.sidebar:
    st.subheader("系统状态")
    st.write(f"允许的格式：{'、'.join(ALLOWED_SUFFIXES)}")
    st.metric("已收文档", f"{len(docs)} 份")
    st.metric("切出的总块数", sum(d["chunk_count"] or 0 for d in docs))
    st.divider()
    st.caption("现在只能「收」和「看」。")
    st.caption("问答、检索、引用溯源都还没做 —— 那是 M2 的事。")
    st.divider()
    st.caption("数据存在项目的 data/ 目录里，关掉页面也在。")

tab_upload, tab_library, tab_chunks = st.tabs(["上传文档", "文档库", "看切分效果"])


with tab_upload:
    st.write("传一个文件进来，系统会把里面的文字掏出来、切成小块、存到磁盘。")

    up = st.file_uploader(
        "选择文件", type=[s.lstrip(".") for s in ALLOWED_SUFFIXES]
    )

    if up is None:
        st.info("还没选文件。支持 .pdf / .txt / .md —— 拖一个进来试试。")
    else:
        raw = up.getvalue()
        st.write(
            f"文件名：`{up.name}` ｜ 大小：**{len(raw) / 1024:.1f} KB** ｜ "
            f"浏览器报的类型：`{up.type or '(空)'}`"
        )

        if st.button("收进来", type="primary"):
            try:
                result = ingest_document(up.name, up.type, raw)
            except (IngestError, StorageError) as e:
                st.error(f"没收进来：{e}")
            else:
                st.success(f"收好了。doc_id = `{result['doc_id']}`")
                c1, c2, c3 = st.columns(3)
                c1.metric("解析出文字", f"{result['text_length']} 字")
                c2.metric("切成小块", f"{result['chunk_count']} 块")
                c3.metric("文件大小", f"{result['size_bytes'] / 1024:.1f} KB")

                st.write("第一块长这样（后面问答时，就是从这些块里捞证据）：")
                st.code(result["first_chunk"], language=None)


with tab_library:
    if not docs:
        st.info("文档库是空的。先去「上传文档」传一份。")
    else:
        st.write(f"已经收进来 {len(docs)} 份文档：")
        st.dataframe(
            [
                {
                    "doc_id": d["doc_id"],
                    "文件名": d["filename"],
                    "大小(KB)": d["size_kb"],
                    "文字数": d["text_length"],
                    "块数": d["chunk_count"],
                    "上传时间": (d["uploaded_at"] or "")[:19],
                }
                for d in docs
            ],
            hide_index=True,
        )
        st.caption("这些内容都躺在项目的 data/chunks/ 目录里。")


with tab_chunks:
    if not docs:
        st.info("还没有文档可看。先去「上传文档」传一份。")
    else:
        options = {f"{d['filename']}  ({d['doc_id']})": d["doc_id"] for d in docs}
        picked = st.selectbox("选一份文档", list(options))
        data = load_chunks(options[picked])
        text = data["text"]

        st.divider()
        st.subheader("拖动滑块，看切分参数怎么影响结果")

        col1, col2 = st.columns(2)
        size = col1.slider("chunk_size —— 每块最多多少字", 50, 1000, 500, 50)
        overlap = col2.slider("chunk_overlap —— 相邻块重叠多少字", 0, 200, 50, 10)

        if overlap >= size:
            st.error("重叠必须小于块大小，否则会一直切下去、停不下来。")
        else:
            chunks = split_text(text, ChunkConfig(chunk_size=size, chunk_overlap=overlap))
            m1, m2 = st.columns(2)
            m1.metric("切成多少块", f"{len(chunks)} 块")
            m2.metric("原文多少字", f"{len(text)} 字")

            if len(chunks) >= 2:
                head_of_2nd = chunks[1][:40]
                overlapped = chunks[0][-40:] == head_of_2nd[:40] or head_of_2nd in chunks[0]
                st.write(
                    "第 2 块的开头（能看到它是从上一块尾巴接过来的，"
                    "所以常常是半句话甚至半个词）："
                )
                st.code(head_of_2nd, language=None)

            st.write("每一块：")
            for i, c in enumerate(chunks):
                with st.expander(f"第 {i} 块 · {len(c)} 字"):
                    st.text(c)
