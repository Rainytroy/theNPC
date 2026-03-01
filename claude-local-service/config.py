import os
from typing import Optional
try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings

class Settings(BaseSettings):
    # Claude API 配置 (Azure)
    azure_claude_api_key: str = ""
    azure_claude_api_url: str = ""
    azure_claude_model: str = "claude-sonnet-4-5"

    # 当前激活配置
    active_config: str = "azure"
    active_model: str = "claude-sonnet-4-5"
    
    # 服务器配置
    host: str = "127.0.0.1"
    port: int = 8000
    
    # 其他配置
    max_tokens: int = 4096
    temperature: float = 0.7
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

def get_settings() -> Settings:
    return Settings()
