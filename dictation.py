from pydantic import BaseModel, Field, field_validator


class UploadRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    size_kb: int = Field(gt=0, le=51200)
    tags: list[str] = Field(default_factory=list)

    @field_validator("filename")
    @classmethod
    def check_suffix(cls, v: str) -> str:
        if not v.lower().endswith((".pdf", ".txt", ".md")):
            raise ValueError("只支持 .pdf / .txt / .md 格式")
        return v


# 测试
if __name__ == "__main__":
    print(UploadRequest(filename="a.pdf", size_kb=120))          # 正常
    print(UploadRequest(filename="a.pdf", size_kb=120, tags=["rag"]))
    try:
        UploadRequest(filename="a.exe", size_kb=120)             # 后缀错
    except Exception as e:
        print("拦截：", e)
    try:
        UploadRequest(filename="a.pdf", size_kb=0)               # 大小为 0
    except Exception as e:
        print("拦截：", e)
