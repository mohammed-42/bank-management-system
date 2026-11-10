"""Streamlit web UI for the banking system.

Run with: streamlit run app.py

This file only draws the screens. All banking rules stay in bank.py and all
database access stays in db.py, so the command-line app (main.py) still works.
"""

import re

import streamlit as st

import bank
import db

# st.dataframe needs pyarrow and pandas. A few locked-down Windows machines
# block those files, so check once and use a plain Markdown table if needed.
try:
    import pandas  # noqa: F401
    import pyarrow  # noqa: F401

    DATAFRAME_AVAILABLE = True
except Exception:
    DATAFRAME_AVAILABLE = False

# Friendly labels used by the history table.
TYPE_LABELS = {
    "deposit": "Deposit",
    "withdraw": "Withdraw",
    "transfer_in": "Transfer In",
    "transfer_out": "Transfer Out",
}

MAX_ATTEMPTS = 3


# --- Startup helpers ---------------------------------------------------------

@st.cache_resource
def _check_database():
    """Ping MongoDB and create the unique index once per session."""
    db.ping()
    db.create_indexes()
    return True


def database_ready():
    """Return True if MongoDB is reachable, otherwise show a friendly error."""
    try:
        _check_database()
        return True
    except RuntimeError as exc:
        # For example MONGO_URI is missing from .env
        st.error(f"Configuration error: {exc}")
    except Exception as exc:
        st.error(db.explain_error(exc))
    return False


def init_state():
    """Create the session_state values we use to remember the login."""
    defaults = {
        "logged_in": False,
        "account_no": None,
        "account_name": "",
        "login_attempts": 0,
        "login_blocked": False,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


# --- Create account ----------------------------------------------------------

def create_account_page():
    """Form that creates a new account using bank.create_account."""
    st.title("Create Account")
    st.write(
        f"Open a new account. The minimum opening balance is "
        f"₹{bank.MIN_OPENING_BALANCE}."
    )

    with st.form("create_account_form"):
        name = st.text_input("Full name", key="create_name")
        pin = st.text_input(
            "4-digit PIN",
            type="password",
            max_chars=4,
            help="Your PIN is stored as a bcrypt hash, never as plain text.",
            key="create_pin",
        )
        opening = st.number_input(
            "Opening balance (₹)",
            min_value=bank.MIN_OPENING_BALANCE,
            step=100,
            value=bank.MIN_OPENING_BALANCE,
            key="create_opening",
        )
        submitted = st.form_submit_button("Create Account")

    if not submitted:
        return

    try:
        success, message = bank.create_account(name, pin, int(opening))
    except Exception as exc:
        # Any unexpected database problem becomes a friendly message.
        st.error(db.explain_error(exc))
        return

    if not success:
        st.error(message)
        return

    st.success(message)
    # bank.create_account puts the account number in the message, so show it big.
    match = re.search(r"\b(\d{8})\b", message)
    if match:
        st.metric("Your account number", match.group(1))


# --- Login -------------------------------------------------------------------

def _record_failed_attempt(message):
    """Count a failed login and block the session after MAX_ATTEMPTS."""
    attempts = st.session_state.login_attempts + 1
    st.session_state.login_attempts = attempts

    if attempts >= MAX_ATTEMPTS:
        st.session_state.login_blocked = True
        st.error("Too many failed attempts. Login is blocked for this session.")
    else:
        left = MAX_ATTEMPTS - attempts
        st.error(f"{message} Attempts left: {left}.")


def _try_login(account_text, pin):
    """Check the login details with bank.login and save the session on success."""
    account_text = account_text.strip()

    # An account number must be digits. Count it as a failed attempt.
    if not account_text.isdigit():
        _record_failed_attempt("Account number must contain digits only.")
        return

    try:
        account, error = bank.login(int(account_text), pin)
    except Exception as exc:
        st.error(db.explain_error(exc))
        return

    # A database/configuration problem is not a wrong PIN, so do not count it.
    if error:
        st.error(error)
        return

    if account is None:
        _record_failed_attempt("Invalid account number or PIN.")
        return

    # Login worked: remember the account and start a fresh private menu.
    st.session_state.logged_in = True
    st.session_state.account_no = account["account_no"]
    st.session_state.account_name = account["name"]
    st.session_state.login_attempts = 0
    st.session_state.login_blocked = False
    st.session_state.pop("private_menu", None)
    st.rerun()


def login_page():
    """Login form with a maximum of three wrong attempts per session."""
    st.title("Login")

    if st.session_state.login_blocked:
        st.warning(
            "Too many failed attempts. Login is blocked for this session. "
            "Restart the app (or refresh the browser) to try again."
        )
        return

    with st.form("login_form"):
        account_text = st.text_input("Account number", key="login_account")
        pin = st.text_input(
            "PIN", type="password", max_chars=4, key="login_pin"
        )
        submitted = st.form_submit_button("Login")

    if submitted:
        _try_login(account_text, pin)


# --- Logged-in pages ---------------------------------------------------------

def dashboard_page():
    """Welcome message and the current balance in a large metric."""
    st.title("Dashboard")
    st.subheader(f"Welcome, {st.session_state.account_name}")
    st.caption(f"Account number: {st.session_state.account_no}")

    try:
        success, result = bank.get_balance(st.session_state.account_no)
    except Exception as exc:
        st.error(db.explain_error(exc))
        return

    if success:
        st.metric("Current Balance", f"₹{result}")
    else:
        st.error(result)


def deposit_page():
    """Deposit money into the logged-in account."""
    st.title("Deposit")
    amount = st.number_input(
        "Amount to deposit (₹)", min_value=1, step=100, value=100,
        key="deposit_amount",
    )

    if not st.button("Deposit", key="deposit_button"):
        return

    try:
        success, message = bank.deposit(st.session_state.account_no, int(amount))
    except Exception as exc:
        st.error(db.explain_error(exc))
        return

    if success:
        st.success(message)
    else:
        st.error(message)


def withdraw_page():
    """Withdraw money, never allowing a negative balance."""
    st.title("Withdraw")
    amount = st.number_input(
        "Amount to withdraw (₹)", min_value=1, step=100, value=100,
        key="withdraw_amount",
    )

    if not st.button("Withdraw", key="withdraw_button"):
        return

    try:
        success, message = bank.withdraw(st.session_state.account_no, int(amount))
    except Exception as exc:
        st.error(db.explain_error(exc))
        return

    if success:
        st.success(message)
    else:
        st.error(message)


def transfer_page():
    """Transfer money to another account."""
    st.title("Transfer")
    receiver_text = st.text_input("Receiver account number", key="transfer_receiver")
    amount = st.number_input(
        "Amount to transfer (₹)", min_value=1, step=100, value=100,
        key="transfer_amount",
    )

    if not st.button("Transfer", key="transfer_button"):
        return

    receiver_text = receiver_text.strip()
    if not receiver_text.isdigit():
        st.error("Receiver account number must contain digits only.")
        return

    receiver_no = int(receiver_text)
    if receiver_no == st.session_state.account_no:
        st.error("You cannot transfer money to the same account.")
        return

    try:
        success, message = bank.transfer(
            st.session_state.account_no, receiver_no, int(amount)
        )
    except Exception as exc:
        st.error(db.explain_error(exc))
        return

    if success:
        st.success(message)
    else:
        st.error(message)


def history_page():
    """Show the last 10 transactions, newest first."""
    st.title("Transaction History")

    try:
        success, result = bank.get_history(st.session_state.account_no)
    except Exception as exc:
        st.error(db.explain_error(exc))
        return

    if not success:
        st.error(result)
        return

    if not result:
        st.info("No transactions yet.")
        return

    rows = []
    for tx in result:
        rows.append({
            "Type": TYPE_LABELS.get(tx["type"], tx["type"]),
            "Amount": tx["amount"],
            "Balance After": tx["balance_after"],
            "Date": tx["date"].strftime("%d-%m-%Y %I:%M %p"),
        })

    if DATAFRAME_AVAILABLE:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        # Fallback for machines where pyarrow/pandas cannot load.
        lines = [
            "| Type | Amount | Balance After | Date |",
            "| --- | ---: | ---: | --- |",
        ]
        for row in rows:
            lines.append(
                f"| {row['Type']} | {row['Amount']} | "
                f"{row['Balance After']} | {row['Date']} |"
            )
        st.markdown("\n".join(lines))


def logout():
    """Forget the login and go back to the public menu."""
    for key in (
        "logged_in", "account_no", "account_name",
        "login_attempts", "login_blocked",
    ):
        st.session_state.pop(key, None)

    # public_menu is not drawn in this run, so it is safe to reset it.
    st.session_state.pop("public_menu", None)
    st.rerun()


# --- Main app ----------------------------------------------------------------

def main():
    st.set_page_config(page_title="Basic Banking System", layout="centered")
    init_state()

    st.sidebar.title("Basic Banking")
    st.sidebar.caption("Python + MongoDB Atlas")

    if not database_ready():
        st.stop()

    if not st.session_state.logged_in:
        # Logged out: only these two pages are available.
        page = st.sidebar.radio(
            "Menu", ["Create Account", "Login"], key="public_menu"
        )

        if page == "Create Account":
            create_account_page()
        else:
            login_page()
        return

    # Logged in: show the account pages.
    st.sidebar.caption(f"Signed in as {st.session_state.account_name}")
    page = st.sidebar.radio(
        "Menu",
        [
            "Dashboard",
            "Deposit",
            "Withdraw",
            "Transfer",
            "Transaction History",
            "Logout",
        ],
        key="private_menu",
    )

    if page == "Dashboard":
        dashboard_page()
    elif page == "Deposit":
        deposit_page()
    elif page == "Withdraw":
        withdraw_page()
    elif page == "Transfer":
        transfer_page()
    elif page == "Transaction History":
        history_page()
    else:
        logout()


if __name__ == "__main__":
    main()
