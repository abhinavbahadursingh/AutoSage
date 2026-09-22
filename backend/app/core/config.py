"""Application settings and environment validation."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    APP_ENV: str = "development"
    DEBUG: bool = True
    APP_SECRET_KEY: str = "insecure-default-change-me"
    
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/autosage"
    
    # Redis & Broker
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # MLflow
    MLFLOW_TRACKING_URI: str = "http://localhost:5000"
    
    # LLM Providers
    GROQ_API_KEY: Optional[str] = None
    OPENROUTER_API_KEY: Optional[str] = None
    HUGGINGFACE_API_TOKEN: Optional[str] = None
    
    # Sandbox
    DOCKER_SANDBOX_IMAGE: str = "autosage-runner:latest"
    SANDBOX_TIMEOUT_SECONDS: int = 300
    
    # Paths
    UPLOAD_DIR: str = "./data/uploads"
    ARTIFACT_DIR: str = "./data/artifacts"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
