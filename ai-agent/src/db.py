from pymongo import MongoClient
from pymongo.database import Database
from src.config import MONGODB_URI, MONGODB_DB_NAME

_client: MongoClient | None = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(MONGODB_URI)
    return _client


def get_db() -> Database:
    return get_client()[MONGODB_DB_NAME]
