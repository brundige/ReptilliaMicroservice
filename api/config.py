# api/config.py

"""
Configuration for the Reptilia API.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # MongoDB
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_database: str = "reptilia"

    # API
    api_title: str = "Reptilia API"
    api_version: str = "1.0.0"
    api_prefix: str = "/api"

    # CORS (for React Native)
    cors_origins: list[str] = ["*"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
