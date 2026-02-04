from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "sqlite:///./sql_app.db"
    
    # Telegram
    BOT_TOKEN: Optional[str] = None
    WEB_URL: Optional[str] = None
    
    # Yandex Alice (Smart Home)
    ALICE_CLIENT_ID: str = "my-smart-home"
    ALICE_CLIENT_SECRET: str = "supersecret123"
    
    # Security
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": True
    }

settings = Settings()
