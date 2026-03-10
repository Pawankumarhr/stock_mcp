"""
portfolio/db.py  —  SQLite database layer for the stock portfolio simulator.

Tables
------
users           : id, username, created_at
transactions    : id, user_id, symbol, company_name, action (BUY/SELL),
                  quantity, price_per_share, total_amount, transaction_date,
                  created_at
"""

import sqlite3
import os
from datetime import datetime

DB_DIR  = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DB_DIR, "portfolio.db")


def _connect():
    """Return a connection with row_factory set."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = _connect()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT    NOT NULL UNIQUE,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            symbol          TEXT    NOT NULL,
            company_name    TEXT    NOT NULL,
            action          TEXT    NOT NULL CHECK (action IN ('BUY', 'SELL')),
            quantity        INTEGER NOT NULL CHECK (quantity > 0),
            price_per_share REAL    NOT NULL,
            total_amount    REAL    NOT NULL,
            transaction_date TEXT   NOT NULL,
            created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)
    conn.commit()
    conn.close()


# ── User operations ──────────────────────────────────────────────────────

def create_user(username: str) -> dict:
    """Create a new user.  Returns {'id': ..., 'username': ...} or raises."""
    conn = _connect()
    try:
        cur = conn.execute(
            "INSERT INTO users (username) VALUES (?)", (username,)
        )
        conn.commit()
        return {"id": cur.lastrowid, "username": username}
    except sqlite3.IntegrityError:
        raise ValueError(f"Username '{username}' already exists.")
    finally:
        conn.close()


def list_users() -> list[dict]:
    """Return all users as a list of dicts."""
    conn = _connect()
    rows = conn.execute(
        "SELECT id, username, created_at FROM users ORDER BY id"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user(user_id: int) -> dict | None:
    """Fetch a single user by ID."""
    conn = _connect()
    row = conn.execute(
        "SELECT id, username, created_at FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ── Transaction operations ───────────────────────────────────────────────

def add_transaction(
    user_id: int,
    symbol: str,
    company_name: str,
    action: str,           # 'BUY' or 'SELL'
    quantity: int,
    price_per_share: float,
    transaction_date: str,  # 'YYYY-MM-DD'
) -> dict:
    """Record a BUY or SELL transaction."""
    total = round(quantity * price_per_share, 2)
    conn = _connect()
    cur = conn.execute(
        """INSERT INTO transactions
           (user_id, symbol, company_name, action, quantity,
            price_per_share, total_amount, transaction_date)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, symbol, company_name, action, quantity,
         price_per_share, total, transaction_date),
    )
    conn.commit()
    conn.close()
    return {
        "txn_id": cur.lastrowid,
        "action": action,
        "symbol": symbol,
        "quantity": quantity,
        "price_per_share": price_per_share,
        "total_amount": total,
        "transaction_date": transaction_date,
    }


def get_holdings(user_id: int) -> list[dict]:
    """Aggregate holdings for a user (net shares per symbol).
    Returns list of dicts: symbol, company_name, total_shares, avg_buy_price, total_invested.
    """
    conn = _connect()
    rows = conn.execute("""
        SELECT
            symbol,
            company_name,
            SUM(CASE WHEN action = 'BUY'  THEN  quantity ELSE 0 END) AS bought,
            SUM(CASE WHEN action = 'SELL' THEN  quantity ELSE 0 END) AS sold,
            SUM(CASE WHEN action = 'BUY'  THEN  total_amount ELSE 0 END) AS total_buy_cost,
            SUM(CASE WHEN action = 'SELL' THEN  total_amount ELSE 0 END) AS total_sell_revenue
        FROM transactions
        WHERE user_id = ?
        GROUP BY symbol
    """, (user_id,)).fetchall()
    conn.close()

    holdings = []
    for r in rows:
        net = r["bought"] - r["sold"]
        if net > 0:
            avg_price = r["total_buy_cost"] / r["bought"] if r["bought"] else 0
            holdings.append({
                "symbol": r["symbol"],
                "company_name": r["company_name"],
                "total_shares": net,
                "avg_buy_price": round(avg_price, 2),
                "total_invested": round(avg_price * net, 2),
            })
    return holdings


def get_transactions(user_id: int, symbol: str | None = None) -> list[dict]:
    """Return transaction history for a user, optionally filtered by symbol."""
    conn = _connect()
    if symbol:
        rows = conn.execute(
            """SELECT * FROM transactions
               WHERE user_id = ? AND symbol = ?
               ORDER BY transaction_date DESC, id DESC""",
            (user_id, symbol),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT * FROM transactions
               WHERE user_id = ?
               ORDER BY transaction_date DESC, id DESC""",
            (user_id,),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_shares_owned(user_id: int, symbol: str) -> int:
    """Quick helper: how many shares of *symbol* does this user own?"""
    conn = _connect()
    row = conn.execute("""
        SELECT
            COALESCE(SUM(CASE WHEN action='BUY' THEN quantity ELSE 0 END), 0)
          - COALESCE(SUM(CASE WHEN action='SELL' THEN quantity ELSE 0 END), 0)
          AS net
        FROM transactions
        WHERE user_id = ? AND symbol = ?
    """, (user_id, symbol)).fetchone()
    conn.close()
    return row["net"] if row else 0


# Auto-initialize on import
init_db()
