from pymongo import MongoClient

from config import DB_NAME, MONGODB_URI

# Sync MongoClient (serverless-friendly)
mongo_client: MongoClient | None = None


def get_client() -> MongoClient:
    global mongo_client
    if mongo_client is None:
        mongo_client = MongoClient(MONGODB_URI)
    return mongo_client


def get_db():
    """Return sync pymongo database."""
    return get_client()[DB_NAME]
