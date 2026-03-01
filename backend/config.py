import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # App Config
    APP_NAME: str = "theNPC Backend"
    HOST: str = "127.0.0.1"
    PORT: int = 26000
    
    # LLM Service Config
    LLM_SERVICE_URL: str = "http://127.0.0.1:25999"
    
    # Paths
    DATA_DIR: str = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    
    class Config:
        env_file = ".env"

settings = Settings()

# Ensure data directory exists
os.makedirs(settings.DATA_DIR, exist_ok=True)
