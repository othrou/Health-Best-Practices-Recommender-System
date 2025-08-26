import os
from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional
from pathlib import Path # <-- Import Path

class Settings(BaseSettings):
    """
    Loads configuration settings from environment variables.
    """
    GOOGLE_API_KEY: str
    MONGO_URI: str
    MONGO_DB_NAME: str

    QDRANT_URL: str
    QDRANT_API_KEY: str
    QDRANT_COLLECTION_NAME: str
    GEMINI_EMBEDDING_MODEL_NAME: str = "models/text-embedding-004" 
    
    EMBEDDING_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"
    GEMINI_MODEL_NAME: str = "gemini-2.0-flash-lite"

    # Security settings
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "a_very_secret_key_that_should_be_changed")
    JWT_ALGORITHM: str = "HS256"
    
    # Token expiration times
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60  # 60 minutes
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7


    # Variable pour détecter si on est en mode test
    TESTING: bool = False

    class Config:
        # --- CHANGE HERE ---
        # Build a path to the .env file in the project root
        env_file = Path(__file__).resolve().parent.parent / ".env"
        extra = "ignore"

@lru_cache()
def get_settings() -> Settings:
    """
    Returns a cached instance of the Settings object.
    Using lru_cache ensures the .env file is read only once.
    """
    # Si la variable d'environnement TESTING est à True, on change le nom de la BDD
    settings = Settings()
    if os.getenv("TESTING") == "True":
        settings.MONGO_DB_NAME = f"{settings.MONGO_DB_NAME}_test"
    return settings

    