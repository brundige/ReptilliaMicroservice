# api/database.py

"""
MongoDB connection management for the Reptilia API.
"""

from pymongo import MongoClient
from pymongo.database import Database
from typing import Generator

from api.config import get_settings

# Global client instance
_client: MongoClient | None = None


def get_client() -> MongoClient:
    """Get or create MongoDB client."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = MongoClient(settings.mongodb_uri)
    return _client


def get_database() -> Database:
    """Get the reptilia database."""
    settings = get_settings()
    return get_client()[settings.mongodb_database]


def close_connection():
    """Close the MongoDB connection."""
    global _client
    if _client is not None:
        _client.close()
        _client = None


# Dependency for FastAPI
def get_db() -> Generator[Database, None, None]:
    """FastAPI dependency that provides database access."""
    db = get_database()
    try:
        yield db
    finally:
        pass  # Connection pooling handles cleanup
