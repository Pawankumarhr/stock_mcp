"""
portfolio/menu.py  —  Interactive terminal menu for the portfolio simulator.

Flow:
  1. Create User / Select User
  2. Company list → pick one
  3. BUY or SELL → enter quantity + date
  4. View Portfolio / Transaction History
"""

import sys, os

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.live_stock import COMPANIES
from portfolio.db import (
    create_user, list_users, get_user,
    get_holdings, get_transactions,
)
from portfolio.trading import buy_stock, sell_stock, portfolio_summary


# ── display helpers ──────────────────────────────────────────────────────

def _header(title: str):
    print(f"\n{'━' * 60}")
    print(f"  {title}")
    print(f"{'━' * 60}")


def _company_menu():
    """Display company list and return (name, symbol) or None."""
    print("\n  ── US Companies ──")
    for key in ["1", "2", "3", "4", "5"]:
        name, symbol = COMPANIES[key]
        print(f"  [{key:>2}] {name} ({symbol})")
    print("  ── Indian Companies (NSE) ──")
    for key in ["6", "7", "8", "9", "10"]:
        name, symbol = COMPANIES[key]
        print(f"  [{key:>2}] {name} ({symbol})")
    print(f"  [ 0] Back")

    choice = input("\n  Select company: ").strip()
    if choice == "0" or choice not in COMPANIES:
        return None
    return COMPANIES[choice]


def _display_holdings(holdings: list, enriched: bool = False):
    """Pretty-print holdings table."""
    if not holdings:
        print("\n  📭 No holdings yet.")
        return

    if enriched:
        print(f"\n  {'Symbol':<16} {'Company':<28} {'Shares':>7} {'Avg Buy':>10} "
              f"{'Invested':>12} {'Cur Price':>10} {'Value':>12} {'P&L':>12} {'P&L%':>8}")
        print(f"  {'─'*125}")
        for h in holdings:
            cur = h['current_price'] or 0
            val = h['current_value'] or 0
            pnl = h['profit_loss'] or 0
            pct = h['profit_loss_pct'] or 0
            sign = "🟢" if pnl >= 0 else "🔴"
            currency = "₹" if ".NS" in h['symbol'] else "$"
            print(f"  {h['symbol']:<16} {h['company_name']:<28} {h['total_shares']:>7} "
                  f"{currency}{h['avg_buy_price']:>9.2f} {currency}{h['total_invested']:>11.2f} "
                  f"{currency}{cur:>9.2f} {currency}{val:>11.2f} "
                  f"{sign}{currency}{pnl:>10.2f} {pct:>7.2f}%")
    else:
        print(f"\n  {'Symbol':<16} {'Company':<28} {'Shares':>7} {'Avg Buy':>10} {'Invested':>12}")
        print(f"  {'─'*75}")
        for h in holdings:
            currency = "₹" if ".NS" in h['symbol'] else "$"
            print(f"  {h['symbol']:<16} {h['company_name']:<28} {h['total_shares']:>7} "
                  f"{currency}{h['avg_buy_price']:>9.2f} {currency}{h['total_invested']:>11.2f}")


def _display_transactions(txns: list):
    """Pretty-print transaction history."""
    if not txns:
        print("\n  📭 No transactions yet.")
        return
    print(f"\n  {'ID':>5} {'Date':<12} {'Action':<6} {'Symbol':<16} {'Qty':>6} "
          f"{'Price':>10} {'Total':>12}")
    print(f"  {'─'*75}")
    for t in txns:
        currency = "₹" if ".NS" in t['symbol'] else "$"
        action_icon = "🟢" if t['action'] == 'BUY' else "🔴"
        print(f"  {t['id']:>5} {t['transaction_date']:<12} "
              f"{action_icon}{t['action']:<5} {t['symbol']:<16} {t['quantity']:>6} "
              f"{currency}{t['price_per_share']:>9.2f} {currency}{t['total_amount']:>11.2f}")


# ── Step 1: User management ─────────────────────────────────────────────

def _select_or_create_user() -> dict | None:
    """Let user create/pick a user account.  Returns user dict or None."""
    while True:
        _header("👤  USER MANAGEMENT")
        print("  [1] Create new user")
        print("  [2] Select existing user")
        print("  [0] Back to main menu")
        ch = input("\n  Choice: ").strip()

        if ch == "0":
            return None

        if ch == "1":
            name = input("  Enter username: ").strip()
            if not name:
                print("  ⚠️  Username cannot be empty.")
                continue
            try:
                user = create_user(name)
                print(f"  ✅ User '{user['username']}' created (ID: {user['id']})")
                return user
            except ValueError as e:
                print(f"  ⚠️  {e}")

        elif ch == "2":
            users = list_users()
            if not users:
                print("  📭 No users found. Create one first.")
                continue
            print()
            for u in users:
                print(f"  [{u['id']:>3}] {u['username']:<20}  (joined {u['created_at']})")
            uid = input("\n  Enter user ID: ").strip()
            if not uid.isdigit():
                print("  ⚠️  Enter a valid number.")
                continue
            user = get_user(int(uid))
            if not user:
                print("  ⚠️  User not found.")
                continue
            print(f"  ✅ Logged in as '{user['username']}' (ID: {user['id']})")
            return user


# ── Step 2: Portfolio actions menu ───────────────────────────────────────

def _portfolio_actions(user: dict):
    """Main loop once a user is selected."""
    uid = user["id"]
    uname = user["username"]

    while True:
        _header(f"📊  PORTFOLIO — {uname}")
        print("  [1] 📈 Buy stock")
        print("  [2] 📉 Sell stock")
        print("  [3] 💼 View portfolio (with live P&L)")
        print("  [4] 💼 View portfolio (offline, no fetch)")
        print("  [5] 📜 Transaction history")
        print("  [6] 👤 Switch user")
        print("  [0] 🚪 Back to main menu")
        ch = input("\n  Choice: ").strip()

        if ch == "0" or ch == "6":
            return ch  # "6" tells caller to re-pick user

        # ── BUY ──────────────────────────────────────────────────────
        if ch == "1":
            _header("📈  BUY STOCK")
            result = _company_menu()
            if result is None:
                continue
            company_name, symbol = result

            qty_str = input(f"  How many shares of {company_name}? ").strip()
            if not qty_str.isdigit() or int(qty_str) <= 0:
                print("  ⚠️  Enter a valid positive number.")
                continue
            qty = int(qty_str)

            date_str = input("  Date to buy (YYYY-MM-DD, e.g. 2026-01-15): ").strip()
            if len(date_str) != 10 or date_str[4] != '-' or date_str[7] != '-':
                print("  ⚠️  Invalid date format. Use YYYY-MM-DD.")
                continue

            print(f"\n  ⏳ Fetching {symbol} price on {date_str}...")
            try:
                txn = buy_stock(uid, symbol, company_name, qty, date_str)
                currency = "₹" if ".NS" in symbol else "$"
                print(f"  ✅ BOUGHT {txn['quantity']} shares of {symbol} "
                      f"@ {currency}{txn['price_per_share']:.2f} each")
                print(f"     Total: {currency}{txn['total_amount']:.2f}  "
                      f"|  Date: {txn['transaction_date']}")
            except ValueError as e:
                print(f"  ❌ {e}")
            except Exception as e:
                print(f"  ❌ Error: {e}")

        # ── SELL ─────────────────────────────────────────────────────
        elif ch == "2":
            _header("📉  SELL STOCK")
            # Show current holdings first
            holdings = get_holdings(uid)
            if not holdings:
                print("  📭 You don't own any stocks yet. Buy first!")
                continue
            print("  Your current holdings:")
            _display_holdings(holdings)

            result = _company_menu()
            if result is None:
                continue
            company_name, symbol = result

            from portfolio.db import get_shares_owned
            owned = get_shares_owned(uid, symbol)
            if owned <= 0:
                print(f"  ⚠️  You don't own any shares of {symbol}.")
                continue
            print(f"  You own {owned} shares of {symbol}.")

            qty_str = input(f"  How many shares to sell? ").strip()
            if not qty_str.isdigit() or int(qty_str) <= 0:
                print("  ⚠️  Enter a valid positive number.")
                continue
            qty = int(qty_str)

            date_str = input("  Date to sell (YYYY-MM-DD, e.g. 2026-03-10): ").strip()
            if len(date_str) != 10 or date_str[4] != '-' or date_str[7] != '-':
                print("  ⚠️  Invalid date format. Use YYYY-MM-DD.")
                continue

            print(f"\n  ⏳ Fetching {symbol} price on {date_str}...")
            try:
                txn = sell_stock(uid, symbol, company_name, qty, date_str)
                currency = "₹" if ".NS" in symbol else "$"
                print(f"  ✅ SOLD {txn['quantity']} shares of {symbol} "
                      f"@ {currency}{txn['price_per_share']:.2f} each")
                print(f"     Revenue: {currency}{txn['total_amount']:.2f}  "
                      f"|  Date: {txn['transaction_date']}")
            except ValueError as e:
                print(f"  ❌ {e}")
            except Exception as e:
                print(f"  ❌ Error: {e}")

        # ── VIEW PORTFOLIO (live P&L) ────────────────────────────────
        elif ch == "3":
            _header("💼  PORTFOLIO (Live P&L)")
            holdings = get_holdings(uid)
            if not holdings:
                print("  📭 No holdings.")
                continue
            print("  ⏳ Fetching live prices...")
            enriched = portfolio_summary(uid, holdings)
            _display_holdings(enriched, enriched=True)

            # Total summary
            total_inv = sum(h['total_invested'] for h in enriched)
            total_val = sum(h['current_value'] or 0 for h in enriched)
            total_pnl = total_val - total_inv
            pct = (total_pnl / total_inv * 100) if total_inv else 0
            sign = "🟢" if total_pnl >= 0 else "🔴"
            print(f"\n  {'─'*50}")
            print(f"  Total Invested : {total_inv:>12.2f}")
            print(f"  Current Value  : {total_val:>12.2f}")
            print(f"  {sign} Net P&L     : {total_pnl:>12.2f}  ({pct:+.2f}%)")

        # ── VIEW PORTFOLIO (offline) ─────────────────────────────────
        elif ch == "4":
            _header("💼  PORTFOLIO (Offline)")
            holdings = get_holdings(uid)
            _display_holdings(holdings)

        # ── TRANSACTION HISTORY ──────────────────────────────────────
        elif ch == "5":
            _header("📜  TRANSACTION HISTORY")
            print("  [A] All transactions")
            print("  [S] Filter by symbol")
            filt = input("  Choice: ").strip().upper()
            if filt == "S":
                sym = input("  Enter symbol (e.g. WIPRO.NS): ").strip().upper()
                txns = get_transactions(uid, sym)
            else:
                txns = get_transactions(uid)
            _display_transactions(txns)

        else:
            print("  ⚠️  Invalid choice.")


# ── Entry point ──────────────────────────────────────────────────────────

def run_portfolio():
    """Top-level function to launch the portfolio simulator."""
    _header("💰  STOCK PORTFOLIO SIMULATOR")
    print("  Buy & sell stocks at historical prices.")
    print("  All transactions are saved in portfolio.db\n")

    while True:
        user = _select_or_create_user()
        if user is None:
            print("  👋 Exiting portfolio simulator.\n")
            return

        result = _portfolio_actions(user)
        if result == "0":
            print("  👋 Exiting portfolio simulator.\n")
            return
        # result == "6" loops back to user selection


if __name__ == "__main__":
    run_portfolio()
