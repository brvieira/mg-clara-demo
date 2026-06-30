from pymongo import MongoClient
from langgraph.checkpoint.mongodb import MongoDBSaver
from src.config import MONGODB_URI, MONGODB_DB_NAME


def get_checkpointer() -> MongoDBSaver:
    client = MongoClient(MONGODB_URI)
    return MongoDBSaver(client, MONGODB_DB_NAME, "short_term_memory", "checkpoint_writes")
