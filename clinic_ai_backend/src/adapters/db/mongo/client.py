"""MongoDB client module."""
from functools import lru_cache
from pymongo import MongoClient
from pymongo.database import Database

from src.core.config import get_settings


@lru_cache(maxsize=1)
def get_mongo_client() -> MongoClient:
    """Return cached Mongo client."""
    settings = get_settings()
    return MongoClient(settings.mongodb_url)


def get_database() -> Database:
    """Return active Mongo database."""
    settings = get_settings()
    return get_mongo_client()[settings.mongodb_db_name]
