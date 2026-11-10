# Basic Banking System (Python + MongoDB Atlas)

A beginner-friendly command-line banking project. It stores accounts and
transactions in MongoDB Atlas and uses bcrypt to hash 4-digit PINs.

## Features

- Create an account with an auto-generated account number
- Minimum opening balance of ₹500
- Login with account number + 4-digit PIN (3 attempts maximum)
- Deposit money
- Withdraw money (never allows a negative balance)
- Check balance
- Transfer money to another account, with a refund if the credit step fails
- View the last 10 transactions, newest first
- Friendly error messages for invalid input and database problems
- Streamlit web UI (`app.py`) that reuses the same banking rules and database

## Project structure

```
bank/
├── main.py          # command-line menus and user input
├── app.py           # Streamlit web UI (same bank.py / db.py)
├── db.py            # MongoDB connection, collections, indexes
├── bank.py          # banking logic
├── tests/
│   ├── conftest.py  # test database setup
│   └── test_bank.py # pytest tests
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## Setup

### 1. Create a virtual environment

```bash
cd bank
python -m venv venv
```

Activate it:

```bash
# Windows (PowerShell)
venv\Scripts\Activate.ps1

# Windows (CMD)
venv\Scripts\activate.bat

# macOS / Linux
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

`pymongo[srv]` is required so `mongodb+srv://` connection strings work.
It also installs `dnspython`, which is needed to look up the Atlas cluster.

### 3. Create the `.env` file

Copy the example file:

```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Then open `.env` and fill in your own values:

```env
MONGO_URI=mongodb+srv://<username>:<password>@<cluster-name>.xxxxx.mongodb.net
DB_NAME=bank_db
TEST_DB_NAME=bank_test_db
```

- `MONGO_URI` – your MongoDB Atlas connection string. Replace `<username>`,
  `<password>` and `<cluster-name>` with your own details.
- `DB_NAME` – the database used by the app.
- `TEST_DB_NAME` – a separate database used only by pytest, for example
  `bank_test_db`.

**Never commit `.env`.** It is already listed in `.gitignore`.

### 4. Allow your IP in MongoDB Atlas

1. Open your cluster in [MongoDB Atlas](https://cloud.mongodb.com).
2. Go to **Network Access** → **Add IP Address**.
3. Add your current IP, or `0.0.0.0/0` for testing/demo purposes only.

Without this step the app cannot connect and will show a timeout error.

## How to run

Both the CLI and the web UI use the same `.env` file, `db.py` and `bank.py`.

### Command-line app

```bash
python main.py
```

The app pings the database first. If the connection fails, it prints a
friendly message instead of crashing.

### Web UI (Streamlit)

```bash
streamlit run app.py
```

Then open the URL shown in the terminal (usually
`http://localhost:8501`). The sidebar switches between the screens:

- Logged out: **Create Account**, **Login**
- Logged in: **Dashboard**, **Deposit**, **Withdraw**, **Transfer**,
  **Transaction History**, **Logout**

The web UI uses the same rules as the CLI: 4-digit PINs hashed with bcrypt,
minimum opening balance of ₹500, no negative balances, and a maximum of three
wrong login attempts per session.

## Menu

Main menu:

1. Create account
2. Login
3. Exit

After login:

1. Deposit
2. Withdraw
3. Check balance
4. Transfer
5. Transaction history (last 10)
6. Logout

Example session:

```
Deposit successful. New balance: ₹5500
```

## Collection design

### `accounts`

| Field        | Type     | Notes                              |
| ------------ | -------- | ---------------------------------- |
| `account_no` | int      | Unique, 8 digits                   |
| `name`       | string   | Account holder's name              |
| `pin_hash`   | string   | bcrypt hash, never the plain PIN   |
| `balance`    | int      | Balance in rupees                  |
| `created_at` | datetime | UTC creation time                  |

A unique index is created on `account_no`.

### `transactions`

| Field           | Type     | Notes                                            |
| --------------- | -------- | ------------------------------------------------ |
| `account_no`    | int      | Owner of this transaction record                 |
| `type`          | string   | `deposit`, `withdraw`, `transfer_in`, `transfer_out` |
| `amount`        | int      | Amount in rupees                                 |
| `balance_after` | int      | Balance after the operation                      |
| `other_account` | int/null | The other account for transfers                  |
| `date`          | datetime | UTC time of the transaction                      |

Every balance change writes a transaction record. A transfer writes one
`transfer_out` record for the sender and one `transfer_in` record for the
receiver.

## Tests

Tests use the separate database from `TEST_DB_NAME` (default `bank_test_db`),
so your real `bank_db` data is never touched. The test database is cleared
before and after each test.

```bash
pytest -v
```

The tests cover:

- Deposit and its transaction record
- Withdraw and its transaction record
- Withdraw with insufficient balance (balance stays unchanged)
- Transfer, including both transaction records and both balances
- Transfer to the same account, a missing account, and insufficient balance
- Invalid deposit amounts

## Troubleshooting

| Problem | Fix |
| ------- | --- |
| `ServerSelectionTimeoutError` | Check internet and add your IP in Atlas **Network Access**. |
| `Authentication failed` | Check the username/password in `MONGO_URI`. |
| `dnspython` / DNS error | Run `pip install "pymongo[srv]"`. |
| `MONGO_URI is missing` | Copy `.env.example` to `.env` and fill it in. |
| Tests accidentally hit the real DB | Make sure `TEST_DB_NAME` is different from `DB_NAME`. |

## Screenshots

Add your project screenshots here before submitting.

### Command-line app

- Main menu
- Create account
- Login and account menu
- Deposit / withdraw messages
- Transfer and transaction history

### Web UI (Streamlit)

- Sidebar with Create Account / Login
- Create Account form and generated account number
- Login screen and the 3-attempt warning
- Dashboard with the large balance metric
- Deposit and Withdraw screens
- Transfer screen with success / error messages
- Transaction History table
- Atlas collections view (`accounts` and `transactions`)

## Notes for submission

- PINs are hashed with bcrypt and are never printed or logged.
- Withdraw uses a `balance >= amount` filter plus `$inc`, so the balance
  can never become negative.
- The transfer first debits the sender, then credits the receiver. If the
  credit fails, the sender is refunded.
