"""Tests for deposit, withdraw and transfer."""

import bank
import db


def make_account(name, opening_balance=1000):
    """Create a test account and return its saved document."""
    success, message = bank.create_account(name, "1234", opening_balance)
    assert success, message

    account = db.accounts_collection().find_one({"name": name})
    assert account is not None
    return account


def test_deposit_increases_balance_and_saves_transaction():
    account = make_account("Alice")

    success, message = bank.deposit(account["account_no"], 250)

    assert success is True
    assert "₹1250" in message

    success, balance = bank.get_balance(account["account_no"])
    assert success is True
    assert balance == 1250

    transaction = db.transactions_collection().find_one({
        "account_no": account["account_no"],
        "type": "deposit",
        "amount": 250,
    })
    assert transaction is not None
    assert transaction["balance_after"] == 1250


def test_withdraw_reduces_balance_and_saves_transaction():
    account = make_account("Bob")

    success, message = bank.withdraw(account["account_no"], 300)

    assert success is True
    assert "₹700" in message

    success, balance = bank.get_balance(account["account_no"])
    assert success is True
    assert balance == 700

    transaction = db.transactions_collection().find_one({
        "account_no": account["account_no"],
        "type": "withdraw",
        "amount": 300,
    })
    assert transaction is not None
    assert transaction["balance_after"] == 700


def test_withdraw_with_insufficient_balance_is_rejected():
    account = make_account("Charlie", opening_balance=500)

    success, message = bank.withdraw(account["account_no"], 1000)

    assert success is False
    assert "Insufficient balance" in message

    # The balance must not change and no withdraw record may be saved.
    success, balance = bank.get_balance(account["account_no"])
    assert success is True
    assert balance == 500

    count = db.transactions_collection().count_documents({
        "account_no": account["account_no"],
        "type": "withdraw",
    })
    assert count == 0


def test_transfer_moves_money_and_saves_both_records():
    sender = make_account("Sender", opening_balance=1000)
    receiver = make_account("Receiver", opening_balance=500)

    success, message = bank.transfer(
        sender["account_no"], receiver["account_no"], 400
    )

    assert success is True
    assert "₹600" in message

    success, sender_balance = bank.get_balance(sender["account_no"])
    assert success is True
    assert sender_balance == 600

    success, receiver_balance = bank.get_balance(receiver["account_no"])
    assert success is True
    assert receiver_balance == 900

    out_record = db.transactions_collection().find_one({
        "account_no": sender["account_no"],
        "type": "transfer_out",
        "amount": 400,
    })
    assert out_record is not None
    assert out_record["balance_after"] == 600
    assert out_record["other_account"] == receiver["account_no"]

    in_record = db.transactions_collection().find_one({
        "account_no": receiver["account_no"],
        "type": "transfer_in",
        "amount": 400,
    })
    assert in_record is not None
    assert in_record["balance_after"] == 900
    assert in_record["other_account"] == sender["account_no"]


def test_transfer_to_same_account_is_rejected():
    account = make_account("Solo")

    success, message = bank.transfer(account["account_no"], account["account_no"], 100)

    assert success is False
    assert "same account" in message

    success, balance = bank.get_balance(account["account_no"])
    assert success is True
    assert balance == 1000


def test_transfer_to_missing_account_is_rejected():
    account = make_account("Real")

    success, message = bank.transfer(account["account_no"], 99999999, 100)

    assert success is False
    assert "Receiver account not found" in message

    success, balance = bank.get_balance(account["account_no"])
    assert success is True
    assert balance == 1000


def test_transfer_with_insufficient_balance_is_rejected():
    sender = make_account("Low", opening_balance=500)
    receiver = make_account("High", opening_balance=500)

    success, message = bank.transfer(
        sender["account_no"], receiver["account_no"], 800
    )

    assert success is False
    assert "Insufficient balance" in message

    success, sender_balance = bank.get_balance(sender["account_no"])
    assert success is True
    assert sender_balance == 500

    success, receiver_balance = bank.get_balance(receiver["account_no"])
    assert success is True
    assert receiver_balance == 500


def test_deposit_rejects_invalid_amounts():
    account = make_account("Valid")

    for amount in (0, -100):
        success, message = bank.deposit(account["account_no"], amount)
        assert success is False
        assert "positive" in message
