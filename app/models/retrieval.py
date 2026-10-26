"""检索相关的数据模型。

这里只定义「形状」，不放检索算法（算法在 services/retriever.py）。
分开的理由跟别处一样：模型层回答「数据长什么样」，
服务层回答「怎么算出来」，混在一起改的时候容易两边一起坏。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class CorpusChunk(BaseModel):
    """检索库里的一条记录：**一个片段** + 它从哪来。

    为什么非带来源不可？因为检索的结果必须能被回头核对。
    只给一句"它是这么说的"没法验证，必须能回答
    「这句话来自哪个文件的第几块」。
    """

    global_index: int = Field(..., ge=0, description="在整个库里的序号，从 0 开始")
    doc_id: str = Field(..., description="文档 id，能拿它回磁盘读原文")
    filename: str = Field(..., description="原始文件名，给人看的")
    chunk_index: int = Field(..., ge=0, description="在该文档内的片段序号，从 0 开始")
    text: str = Field(..., description="片段原文")


class Candidate(BaseModel):
    """一个候选片段：检索交出来的成品。

    注意三点：
      1. 刻意**没有** page 字段 —— 现有 PDF .extract_text 拿不到页码，
         编一个写上去就是编数据。来源只到「哪个文件第几块」这一层。
      2. score 的含义随检索方式变化：关键词检索是「命中次数」（整数，越大越好），
         向量检索是「余弦相似度」（-1~1，越大越像）。**两者不能直接比大小**。
      3. 混合检索（hybrid）的 score 是 RRF 融合分，由各路**名次**算出
         （`sum(1 / (60 + rank))`）。它既不是概率，也不是答案正确率，
         更不能跟上面两种分数混着排 —— 脱离 rank 看这个数字没有意义。
    """

    rank: int = Field(..., ge=1, description="名次，1 表示最靠前")
    score: float = Field(..., description="得分，含义由检索方式决定，见上")
    chunk_index: int = Field(..., ge=0, description="文档内片段序号，从 0 开始")
    doc_id: str
    filename: str
    text: str
