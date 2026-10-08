"""文档数据模型。

本模块集中定义「一份上传的文档长什么样」，以及所有校验规则。
接口层、服务层只负责调用，不再重复写 if 判断 —— 把散落各处的校验
收拢到一处，是 Pydantic 在真实项目里最大的价值。
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

ALLOWED_CONTENT_TYPES = ("application/pdf", "text/plain", "text/markdown")
ALLOWED_SUFFIXES = (".pdf", ".txt", ".md")


class ChunkConfig(BaseModel):
    """文本切分参数（嵌套模型的示例）。

    一个模型可以直接当作另一个模型的字段类型。这里的真实约束是
    chunk_overlap 必须小于 chunk_size，否则切分会陷入死循环。
    """

    chunk_size: int = Field(default=500, gt=0, le=2000, description="每块最大字符数")
    chunk_overlap: int = Field(default=50, ge=0, description="相邻块的重叠字符数")

    @model_validator(mode="after")
    def overlap_must_be_smaller(self) -> "ChunkConfig":
        """跨字段校验。

        field_validator 只看得到自己那一个字段，做不了这种「两个字段比大小」，
        所以要用 model_validator —— 它拿到的是整个模型实例。
        """
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError(
                f"chunk_overlap({self.chunk_overlap}) 必须小于 "
                f"chunk_size({self.chunk_size})"
            )
        return self


class DocumentMeta(BaseModel):
    """文档元数据：项目中每份上传文档的统一描述。"""

    doc_id: str = Field(min_length=1, description="文档唯一标识")
    filename: str = Field(min_length=1, max_length=255, description="原始文件名")
    content_type: Literal["application/pdf", "text/plain", "text/markdown"] = Field(
        description="MIME 类型，只能是这三种之一"
    )
    size_kb: int = Field(gt=0, le=51200, description="文件大小(KB)，上限 50MB")
    chunk_config: ChunkConfig = Field(
        default_factory=ChunkConfig, description="这份文档的切分参数"
    )
    uploaded_at: datetime = Field(default_factory=datetime.now, description="上传时间")
    tags: list[str] = Field(default_factory=list, description="标签，默认空列表")
    source_url: str | None = Field(default=None, description="来源链接，可选")

    @field_validator("filename")
    @classmethod
    def check_filename(cls, v: str) -> str:
        """校验文件名：不能带路径分隔符，后缀必须在白名单里。

        三个硬性要求：① 加 @classmethod ② 第一个参数是 cls
        ③ 末尾必须 return v（忘了返回，字段会变成 None）。
        """
        if "/" in v or "\\" in v:
            raise ValueError("文件名不能包含路径分隔符")
        if not v.lower().endswith(ALLOWED_SUFFIXES):
            raise ValueError(f"只支持 {'、'.join(ALLOWED_SUFFIXES)} 格式")
        return v

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, v: list[str]) -> list[str]:
        """去空白、去空串、去重，并保持原有顺序。

        dict.fromkeys 会按插入顺序保留唯一的键 —— 借它去重比手写 set 更省事，
        也顺便复习一下「Python 的字典是有序的」。
        """
        return list(dict.fromkeys(t.strip() for t in v if t.strip()))
