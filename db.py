"""MongoDB connection, collections and indexes."""

import os

from dotenv import load_dotenv
from pymongo import MongoClient

# Load values from .env into environment variables.
# Existing environment variables are NOT overwritten (useful for tests).
load_dotenv()

# We keep one shared client for the whole program.
_client = None


def get_client():
    """Create the MongoDB client once and return it."""
    global _client
    if _client is None:
        uri = os.getenv("MONGO_URI", "").strip()
        if not uri:
            raise RuntimeError(
                "MONGO_URI is missing. Copy .env.example to .env and fill in your Atlas connection string."
            )
        _client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    return _client


def get_database():
    """Return the database named by DB_NAME in .env."""
    db_name = os.getenv("DB_NAME", "bank_db").strip() or "bank_db"
    return get_client()[db_name]


def accounts_collection():
    """Return the accounts collection."""
    return get_database()["accounts"]


def transactions_collection():
    """Return the transactions collection."""
    return get_database()["transactions"]


def ping():
    """Send a small command to MongoDB to check the connection."""
    get_client().admin.command("ping")


def create_indexes():
    """Create a unique index so two accounts can never share a number."""
    accounts_collection().create_index("account_no", unique=True)


def explain_error(exc):
    """Turn common MongoDB errors into a friendly hint."""
    text = str(exc).lower()

    if "authentication failed" in text or "bad auth" in text:
        return "MongoDB login failed. Check the username and password in .env."
    if "server selection" in text or "timed out" in text or "timeout" in text:
        return (
            "Could not reach MongoDB Atlas. Check your internet connection and add your "
            "current IP address in Atlas > Network Access."
        )
    if "dns" in text or "srv" in text:
        return (
            "Could not look up the Atlas host name. Install pymongo[srv] and check your internet."
        )
    return f"MongoDB error: {exc}"
