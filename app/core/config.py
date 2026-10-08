"""全局配置。

原则：所有「会随环境变化」的东西（密钥、地址、路径、参数）都集中在这里，
代码里其他地方一律不许出现硬编码 —— 换台机器、上线部署时只改 .env 就够了。
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录：本文件位于 app/core/config.py，往上三级即根目录
BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """应用配置。

    字段名会自动去「环境变量」和「.env 文件」里找同名项（不区分大小写）：
        APP_NAME  ->  app_name
        DEBUG     ->  debug
    找不到就用这里写的默认值。
    """

    model_config = SettingsConfigDict(
        # 用绝对路径，避免「从哪个目录启动程序」影响读取结果
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",  # .env 里多出来的键不报错
    )

    # 应用
    app_name: str = "personal-ai-kb"
    debug: bool = False

    # 模型服务
    openai_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    llm_model: str = "qwen3:4b"

    # 数据存储
    data_dir: Path = Path("./data")
    vector_store_dir: Path = Path("./data/vectors")

    # RAG 默认参数
    default_chunk_size: int = 500
    default_chunk_overlap: int = 50
    top_k: int = 5


# 模块级实例化：整个项目 from app.core.config import settings 直接用
settings = Settings()
