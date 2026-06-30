from pymongo import MongoClient
from langgraph.store.mongodb import MongoDBStore
from src.config import MONGODB_URI, MONGODB_DB_NAME


def get_store() -> MongoDBStore:
    client = MongoClient(MONGODB_URI)
    collection = client[MONGODB_DB_NAME]["long_term_memory"]
    return MongoDBStore(collection=collection)
