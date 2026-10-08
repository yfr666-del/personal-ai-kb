"""配置自检脚本。

用法：python check_config.py

验证方法：改一改 .env 里的 DEBUG（true/false），再跑一次，
看输出有没有跟着变 —— 变了才说明配置真的从 .env 生效。
"""

from app.core.config import settings

print("=" * 56)
print("当前生效的配置")
print("=" * 56)
print(f"app_name    = {settings.app_name}")
print(f"debug       = {settings.debug}   (类型: {type(settings.debug).__name__})")
print(f"llm_model   = {settings.llm_model}      <- .env 里没配，用的默认值")
print(f"ollama_url  = {settings.ollama_base_url}")
key = settings.openai_api_key
print(f"openai_key  = {key[:8] + '...' if key else '(空)'}")
print(f"data_dir    = {settings.data_dir}")
print(f"top_k       = {settings.top_k}")
