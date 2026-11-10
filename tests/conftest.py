"""Pytest setup: always use a separate test database."""

import os

from dotenv import load_dotenv
import pytest

load_dotenv()

# This MUST be set before db.py is imported so tests never touch the real database.
os.environ["DB_NAME"] = os.getenv("TEST_DB_NAME", "bank_test_db")

import db  # noqa: E402


@pytest.fixture(autouse=True)
def clean_database():
    """Start and end every test with empty test collections."""
    accounts = db.accounts_collection()
    transactions = db.transactions_collection()

    accounts.delete_many({})
    transactions.delete_many({})
    db.create_indexes()

    yield

    accounts.delete_many({})
    transactions.delete_many({})
