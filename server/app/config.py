from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/followthru"
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    OPENAI_API_KEY: str = ""
    
    class Config:
        # Resolve env file relative to `server/` so running from repo root still works.
        env_file = Path(__file__).resolve().parent.parent / ".env"

settings = Settings()
