# adapters/mongodb/connection.py

"""
MongoDB connection manager for the Reptile Habitat Automation System.

Provides a singleton connection pool and database reference.
Supports both local MongoDB and MongoDB Atlas (mongodb+srv://).
"""

import re
from typing import Optional
from pymongo import MongoClient
from pymongo.database import Database


def _mask_connection_string(uri: str) -> str:
    """Mask password in connection string for safe logging."""
    return re.sub(r'(://[^:]+:)[^@]+(@)', r'\1****\2', uri)


class MongoDBConnection:
    """
    Singleton MongoDB connection manager.

    Usage:
        # Local MongoDB
        conn = MongoDBConnection(uri="mongodb://localhost:27017", database="reptilia")

        # MongoDB Atlas
        conn = MongoDBConnection(
            uri="mongodb+srv://user:password@cluster.mongodb.net/?appName=myapp",
            database="reptilia"
        )

        db = conn.get_database()
        collection = db["sensor_readings"]
    """

    _instance: Optional['MongoDBConnection'] = None
    _client: Optional[MongoClient] = None
    _database: Optional[Database] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        uri: str = "mongodb://localhost:27017",
        database: str = "reptilia"
    ):
        """
        Initialize MongoDB connection.

        Args:
            uri: MongoDB connection URI (supports mongodb:// and mongodb+srv://)
            database: Database name to use
        """
        if self._client is None:
            self._uri = uri
            self._database_name = database
            self._connect()

    def _connect(self):
        """Establish connection to MongoDB."""
        masked_uri = _mask_connection_string(self._uri)
        print(f"Connecting to MongoDB at {masked_uri}...")
        self._client = MongoClient(self._uri)
        self._database = self._client[self._database_name]

        # Test connection
        try:
            self._client.admin.command('ping')
            print(f"  Connected to MongoDB database: {self._database_name}")
        except Exception as e:
            print(f"  MongoDB connection failed: {e}")
            raise

    def get_database(self) -> Database:
        """Get the database reference."""
        if self._database is None:
            self._connect()
        return self._database

    def get_client(self) -> MongoClient:
        """Get the MongoDB client."""
        if self._client is None:
            self._connect()
        return self._client

    def close(self):
        """Close the MongoDB connection."""
        if self._client:
            self._client.close()
            self._client = None
            self._database = None
            print("MongoDB connection closed")

    @classmethod
    def reset(cls):
        """Reset the singleton instance (useful for testing)."""
        if cls._instance and cls._client:
            cls._client.close()
        cls._instance = None
        cls._client = None
        cls._database = None
