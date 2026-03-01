import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "theNPC Backend"
    
    # Paths
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    # DATA_DIR should be theNPC/data. BASE_DIR is theNPC/backend.
    # So we need parent of BASE_DIR.
    DATA_DIR: str = os.path.join(os.path.dirname(BASE_DIR), "data")
    
    # LLM Services
    LLM_SERVICE_URL: str = "http://127.0.0.1:25999" # Default/Claude
    GEMINI_SERVICE_URL: str = "http://127.0.0.1:25998" # Gemini
    
    # Image Service (configure via .env)
    IMAGE_SERVICE_URL: str = ""
    IMAGE_EDIT_URL: str = ""
    GEMINI_API_KEY: str = "" # Used as token for image service
    GEMINI_MODEL: str = "gemini-pro" # Added to match .env

    # Aliyun OSS (configure via .env)
    ALIYUN_ACCESS_KEY_ID: str = ""
    ALIYUN_ACCESS_KEY_SECRET: str = ""
    OSS_BUCKET_NAME: str = ""
    OSS_ENDPOINT: str = ""

    # Server
    HOST: str = "127.0.0.1"
    PORT: int = 26000

    class Config:
        env_file = ".env"

settings = Settings()
