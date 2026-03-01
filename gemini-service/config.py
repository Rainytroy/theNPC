import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-3-pro-preview"
    HOST: str = "127.0.0.1"
    PORT: int = 25998

    class Config:
        env_file = ".env"

settings = Settings()
