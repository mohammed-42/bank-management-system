"""All banking operations."""

import random
from datetime import datetime, timezone

import bcrypt
from pymongo.errors import DuplicateKeyError, PyMongoError

import db

MIN_OPENING_BALANCE = 500


# --- Small helpers -----------------------------------------------------------

def _now():
    """Return the current UTC time (used for created_at and transaction dates)."""
    return datetime.now(timezone.utc)


def _valid_pin(pin):
    """A PIN must be exactly 4 digits."""
    return isinstance(pin, str) and len(pin) == 4 and pin.isdigit()


def _hash_pin(pin):
    """Hash the PIN with bcrypt. The plain PIN is never stored."""
    return bcrypt.hashpw(pin.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _check_pin(pin, pin_hash):
    """Return True if the plain PIN matches the stored bcrypt hash."""
    try:
        return bcrypt.checkpw(pin.encode("utf-8"), pin_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _new_account_number(accounts):
    """Generate a random 8-digit account number that is not already used."""
    while True:
        number = random.randint(10000000, 99999999)
        if accounts.find_one({"account_no": number}, {"_id": 1}) is None:
            return number


def _save_transaction(account_no, tx_type, amount, balance_after, other_account=None):
    """Insert one transaction record. The caller handles database errors."""
    db.transactions_collection().insert_one({
        "account_no": account_no,
        "type": tx_type,
        "amount": amount,
        "balance_after": balance_after,
        "other_account": other_account,
        "date": _now(),
    })


def _balance_of(accounts, account_no):
    """Fetch the current balance, or None if the account does not exist."""
    account = accounts.find_one({"account_no": account_no}, {"balance": 1})
    return None if account is None else account["balance"]


# --- Public banking functions ------------------------------------------------

def create_account(name, pin, opening_balance):
    """Create a new account and return (success, message)."""
    name = name.strip()

    if not name:
        return False, "Name cannot be empty."
    if not _valid_pin(pin):
        return False, "PIN must be exactly 4 digits."
    if not isinstance(opening_balance, int) or opening_balance < MIN_OPENING_BALANCE:
        return False, f"Opening balance must be at least ₹{MIN_OPENING_BALANCE}."

    try:
        accounts = db.accounts_collection()

        # Try a few times in case the random number is taken at the same moment.
        for _ in range(5):
            account_no = _new_account_number(accounts)
            document = {
                "account_no": account_no,
                "name": name,
                "pin_hash": _hash_pin(pin),
                "balance": opening_balance,
                "created_at": _now(),
            }

            try:
                accounts.insert_one(document)
            except DuplicateKeyError:
                continue

            # Save the opening balance as the first transaction.
            try:
                _save_transaction(account_no, "deposit", opening_balance, opening_balance)
                warning = ""
            except PyMongoError:
                warning = " (Warning: opening transaction could not be saved.)"

            return True, (
                f"Account created successfully. Your account number is {account_no}.{warning}"
            )

        return False, "Could not generate a unique account number. Please try again."
    except PyMongoError as exc:
        return False, db.explain_error(exc)


def login(account_no, pin):
    """Check account number and PIN.

    Returns (account, error). On success account is a dict and error is None.
    On wrong details account is None and error is None.
    On a database problem account is None and error is a friendly message.
    """
    try:
        account = db.accounts_collection().find_one({"account_no": account_no})
    except PyMongoError as exc:
        return None, db.explain_error(exc)

    if account is None:
        return None, None

    if _check_pin(pin, account.get("pin_hash", "")):
        return account, None

    return None, None


def deposit(account_no, amount):
    """Add money to an account and return (success, message)."""
    if not isinstance(amount, int) or amount <= 0:
        return False, "Amount must be a positive whole number."

    try:
        accounts = db.accounts_collection()
        result = accounts.update_one(
            {"account_no": account_no},
            {"$inc": {"balance": amount}},
        )

        if result.matched_count == 0:
            return False, "Account not found."

        balance = _balance_of(accounts, account_no)
        warning = ""
        try:
            _save_transaction(account_no, "deposit", amount, balance)
        except PyMongoError:
            warning = " (Warning: transaction record could not be saved.)"

        return True, f"Deposit successful. New balance: ₹{balance}{warning}"
    except PyMongoError as exc:
        return False, db.explain_error(exc)


def withdraw(account_no, amount):
    """Remove money, but only if the balance is high enough."""
    if not isinstance(amount, int) or amount <= 0:
        return False, "Amount must be a positive whole number."

    try:
        accounts = db.accounts_collection()

        # The balance filter + $inc makes it impossible to go below zero.
        result = accounts.update_one(
            {"account_no": account_no, "balance": {"$gte": amount}},
            {"$inc": {"balance": -amount}},
        )

        if result.matched_count == 0:
            # Find out whether the account is missing or the balance is too low.
            if accounts.find_one({"account_no": account_no}, {"_id": 1}) is None:
                return False, "Account not found."
            return False, "Insufficient balance."

        balance = _balance_of(accounts, account_no)
        warning = ""
        try:
            _save_transaction(account_no, "withdraw", amount, balance)
        except PyMongoError:
            warning = " (Warning: transaction record could not be saved.)"

        return True, f"Withdrawal successful. New balance: ₹{balance}{warning}"
    except PyMongoError as exc:
        return False, db.explain_error(exc)


def transfer(sender_no, receiver_no, amount):
    """Move money from one account to another and return (success, message)."""
    if not isinstance(amount, int) or amount <= 0:
        return False, "Amount must be a positive whole number."
    if sender_no == receiver_no:
        return False, "You cannot transfer money to the same account."

    try:
        accounts = db.accounts_collection()

        if accounts.find_one({"account_no": receiver_no}, {"_id": 1}) is None:
            return False, "Receiver account not found."

        # 1. Debit the sender. The balance filter prevents a negative balance.
        debit = accounts.update_one(
            {"account_no": sender_no, "balance": {"$gte": amount}},
            {"$inc": {"balance": -amount}},
        )

        if debit.matched_count == 0:
            return False, "Insufficient balance."

        # 2. Credit the receiver. If anything goes wrong, give the money back.
        try:
            credit = accounts.update_one(
                {"account_no": receiver_no},
                {"$inc": {"balance": amount}},
            )
        except PyMongoError:
            accounts.update_one(
                {"account_no": sender_no},
                {"$inc": {"balance": amount}},
            )
            return False, "Transfer failed. The amount was refunded to your account."

        if credit.matched_count == 0:
            accounts.update_one(
                {"account_no": sender_no},
                {"$inc": {"balance": amount}},
            )
            return False, "Receiver account not found. Transfer cancelled."

        sender_balance = _balance_of(accounts, sender_no)
        receiver_balance = _balance_of(accounts, receiver_no)

        # 3. Save one record for each side of the transfer.
        warning = ""
        try:
            _save_transaction(sender_no, "transfer_out", amount, sender_balance, receiver_no)
            _save_transaction(receiver_no, "transfer_in", amount, receiver_balance, sender_no)
        except PyMongoError:
            warning = " (Warning: transaction records could not be saved.)"

        return True, (
            f"Transfer successful. New balance: ₹{sender_balance} "
            f"(sent ₹{amount} to account {receiver_no}).{warning}"
        )
    except PyMongoError as exc:
        return False, db.explain_error(exc)


def get_balance(account_no):
    """Return (success, balance_or_message)."""
    try:
        balance = _balance_of(db.accounts_collection(), account_no)
    except PyMongoError as exc:
        return False, db.explain_error(exc)

    if balance is None:
        return False, "Account not found."
    return True, balance


def get_history(account_no, limit=10):
    """Return (success, transactions_or_message), newest first."""
    try:
        cursor = (
            db.transactions_collection()
            .find({"account_no": account_no})
            .sort("date", -1)
            .limit(limit)
        )
        return True, list(cursor)
    except PyMongoError as exc:
        return False, db.explain_error(exc)
