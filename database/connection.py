"""Conexión a MongoDB (singleton)."""
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

_client = None

def get_client():
    global _client
    if _client is None:
        _client = MongoClient(config.MONGO_URI, serverSelectionTimeoutMS=5000)
    return _client

def get_db():
    return get_client()[config.MONGO_DB]

def get_champions_collection():
    return get_db()[config.COLLECTION_CHAMPIONS]

def get_items_collection():
    return get_db()[config.COLLECTION_ITEMS]

def test_connection():
    try:
        get_client().admin.command("ping")
        print("✓ Conexión a MongoDB exitosa")
        return True
    except ConnectionFailure as e:
        print(f"✗ Error de conexión: {e}")
        print(f"  Verifica que MongoDB está corriendo en {config.MONGO_URI}")
        return False

if __name__ == "__main__":
    test_connection()
