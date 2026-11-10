"""Menu and user input for the banking system."""

import getpass
import sys

from pymongo.errors import PyMongoError

import bank
import db

# The messages contain ₹. On Windows, redirected output may use cp1252,
# which cannot encode it, so force UTF-8 to avoid a UnicodeEncodeError.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

MENU_WIDTH = 46

TYPE_LABELS = {
    "deposit": "Deposit",
    "withdraw": "Withdraw",
    "transfer_in": "Transfer In",
    "transfer_out": "Transfer Out",
}


# --- Input helpers -----------------------------------------------------------

def ask_amount(prompt):
    """Ask for a positive whole-number amount. Return None for bad input."""
    text = input(prompt).strip()
    if not text:
        print("Amount cannot be empty.")
        return None

    try:
        amount = int(text)
    except ValueError:
        print("Invalid amount. Enter a whole number like 500.")
        return None

    if amount <= 0:
        print("Amount must be greater than 0.")
        return None

    return amount


def ask_pin(prompt="PIN: "):
    """Read a PIN without showing it on the screen."""
    return getpass.getpass(prompt).strip()


# --- Screens -----------------------------------------------------------------

def show_main_menu():
    """Print the main menu."""
    print("\n" + "=" * MENU_WIDTH)
    print("        BASIC BANKING SYSTEM (MongoDB)")
    print("=" * MENU_WIDTH)
    print("1. Create account")
    print("2. Login")
    print("3. Exit")


def show_account_menu(account):
    """Print the menu shown after a successful login."""
    print("\n" + "=" * MENU_WIDTH)
    print(f"  Welcome, {account['name']} (A/C {account['account_no']})")
    print("=" * MENU_WIDTH)
    print("1. Deposit")
    print("2. Withdraw")
    print("3. Check balance")
    print("4. Transfer")
    print("5. Transaction history")
    print("6. Logout")


# --- Menu actions ------------------------------------------------------------

def create_account_flow():
    """Ask for details and create a new account."""
    print("\n--- Create Account ---")
    name = input("Full name: ").strip()
    pin = ask_pin("Choose a 4-digit PIN: ")
    opening_balance = ask_amount(f"Opening balance (minimum ₹{bank.MIN_OPENING_BALANCE}): ")

    if opening_balance is None:
        return

    success, message = bank.create_account(name, pin, opening_balance)
    print(f"\n{message}")


def login_flow():
    """Ask for login details (max 3 attempts) and open the account menu."""
    print("\n--- Login ---")

    for attempt in range(1, 4):
        account_text = input("Account number: ").strip()

        if not account_text.isdigit():
            print("Account number must contain digits only.")
        else:
            pin = ask_pin()

            # Stop immediately if the database itself is having a problem.
            account, error = bank.login(int(account_text), pin)
            if error:
                print(f"\n{error}")
                return

            if account is not None:
                print(f"\nLogin successful. Welcome back, {account['name']}!")
                account_menu(account)
                return

            print("Invalid account number or PIN.")

        remaining = 3 - attempt
        if remaining > 0:
            print(f"{remaining} attempt(s) left.")

    print("\nToo many failed attempts. Returning to the main menu.")


def account_menu(account):
    """Show the logged-in menu until the user logs out."""
    while True:
        show_account_menu(account)
        choice = input("Choose an option (1-6): ").strip()

        if choice == "1":
            deposit_flow(account)
        elif choice == "2":
            withdraw_flow(account)
        elif choice == "3":
            balance_flow(account)
        elif choice == "4":
            transfer_flow(account)
        elif choice == "5":
            history_flow(account)
        elif choice == "6":
            print("\nLogged out successfully.")
            return
        else:
            print("Invalid choice. Please enter a number from 1 to 6.")


def deposit_flow(account):
    """Deposit money into the logged-in account."""
    print("\n--- Deposit ---")
    amount = ask_amount("Amount to deposit: ₹")
    if amount is None:
        return

    success, message = bank.deposit(account["account_no"], amount)
    print(f"\n{message}")


def withdraw_flow(account):
    """Withdraw money from the logged-in account."""
    print("\n--- Withdraw ---")
    amount = ask_amount("Amount to withdraw: ₹")
    if amount is None:
        return

    success, message = bank.withdraw(account["account_no"], amount)
    print(f"\n{message}")


def balance_flow(account):
    """Show the current balance."""
    success, result = bank.get_balance(account["account_no"])
    if success:
        print(f"\nCurrent balance: ₹{result}")
    else:
        print(f"\n{result}")


def transfer_flow(account):
    """Transfer money to another account."""
    print("\n--- Transfer ---")
    receiver_text = input("Receiver account number: ").strip()

    if not receiver_text.isdigit():
        print("Account number must contain digits only.")
        return

    amount = ask_amount("Amount to transfer: ₹")
    if amount is None:
        return

    success, message = bank.transfer(account["account_no"], int(receiver_text), amount)
    print(f"\n{message}")


def history_flow(account):
    """Show the last 10 transactions, newest first."""
    print("\n--- Last 10 Transactions ---")
    success, result = bank.get_history(account["account_no"])

    if not success:
        print(f"\n{result}")
        return

    if not result:
        print("\nNo transactions yet.")
        return

    for tx in result:
        label = TYPE_LABELS.get(tx["type"], tx["type"])
        date_text = tx["date"].strftime("%d-%m-%Y %I:%M %p")

        line = (
            f"{date_text} | {label:<12} | ₹{tx['amount']:>7} "
            f"| Balance: ₹{tx['balance_after']}"
        )
        if tx.get("other_account"):
            line += f" | Other A/C: {tx['other_account']}"

        print(line)


# --- Startup -----------------------------------------------------------------

def connect_database():
    """Ping MongoDB and create indexes. Return True if everything is ready."""
    try:
        db.ping()
        db.create_indexes()
        print("Connected to MongoDB Atlas.")
        return True
    except PyMongoError as exc:
        print("\nCould not connect to MongoDB Atlas.")
        print(db.explain_error(exc))
    except RuntimeError as exc:
        print(f"\nConfiguration error: {exc}")
    except Exception as exc:
        print("\nCould not start the database connection.")
        print(f"Details: {exc}")

    print("\nPlease check .env, your internet connection, and Atlas Network Access.")
    return False


def run():
    """Main program loop."""
    if not connect_database():
        return

    while True:
        show_main_menu()
        choice = input("Choose an option (1-3): ").strip()

        if choice == "1":
            create_account_flow()
        elif choice == "2":
            login_flow()
        elif choice == "3":
            print("\nThank you for using the banking system. Goodbye!")
            return
        else:
            print("Invalid choice. Please enter 1, 2 or 3.")


if __name__ == "__main__":
    try:
        run()
    except (KeyboardInterrupt, EOFError):
        print("\n\nSession closed.")
