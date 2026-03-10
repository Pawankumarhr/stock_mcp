"""
portfolio/trading.py  —  Buy & sell logic with historical price fetching.

Core functions:
    fetch_price_on_date(symbol, date_str)  — get close price from yfinance
    buy_stock(user_id, symbol, company, qty, date_str)
    sell_stock(user_id, symbol, company, qty, date_str)
"""

import yfinance as yf
from datetime import datetime, timedelta
from portfolio.db import add_transaction, get_shares_owned


def fetch_price_on_date(symbol: str, date_str: str) -> float | None:
    """
    Fetch the closing price of *symbol* on *date_str* (YYYY-MM-DD).

    yfinance needs a date range, so we fetch start=date, end=date+1.
    If the exact date is a holiday/weekend, we take the nearest prior
    trading day's close (up to 7 days back).
    """
    target = datetime.strptime(date_str, "%Y-%m-%d")
    # Try up to 7 days back to find a trading day
    start = target - timedelta(days=7)
    end   = target + timedelta(days=1)

    ticker = yf.Ticker(symbol)
    hist = ticker.history(start=start.strftime("%Y-%m-%d"),
                          end=end.strftime("%Y-%m-%d"))

    if hist.empty:
        return None

    # Filter rows up to and including the target date
    hist.index = hist.index.tz_localize(None)  # remove tz for comparison
    valid = hist[hist.index <= target]
    if valid.empty:
        return None

    # Return the close price of the latest available day <= target
    return round(float(valid.iloc[-1]["Close"]), 2)


def fetch_current_price(symbol: str) -> float | None:
    """Fetch the current live price of a symbol."""
    ticker = yf.Ticker(symbol)
    info = ticker.info
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    if price:
        return round(float(price), 2)
    return None


def buy_stock(
    user_id: int,
    symbol: str,
    company_name: str,
    quantity: int,
    date_str: str,
) -> dict:
    """
    Buy *quantity* shares of *symbol* at the closing price on *date_str*.
    Returns transaction dict or raises on error.
    """
    price = fetch_price_on_date(symbol, date_str)
    if price is None:
        raise ValueError(
            f"Could not fetch price for {symbol} on {date_str}. "
            "Possibly the market was closed or data is unavailable."
        )

    txn = add_transaction(
        user_id=user_id,
        symbol=symbol,
        company_name=company_name,
        action="BUY",
        quantity=quantity,
        price_per_share=price,
        transaction_date=date_str,
    )
    return txn


def sell_stock(
    user_id: int,
    symbol: str,
    company_name: str,
    quantity: int,
    date_str: str,
) -> dict:
    """
    Sell *quantity* shares of *symbol* at the closing price on *date_str*.
    Validates that the user owns enough shares (based on all transactions
    with transaction_date <= date_str).
    """
    owned = get_shares_owned(user_id, symbol)
    if owned < quantity:
        raise ValueError(
            f"You only own {owned} shares of {symbol}. Cannot sell {quantity}."
        )

    price = fetch_price_on_date(symbol, date_str)
    if price is None:
        raise ValueError(
            f"Could not fetch price for {symbol} on {date_str}. "
            "Possibly the market was closed or data is unavailable."
        )

    txn = add_transaction(
        user_id=user_id,
        symbol=symbol,
        company_name=company_name,
        action="SELL",
        quantity=quantity,
        price_per_share=price,
        transaction_date=date_str,
    )
    return txn


def portfolio_summary(user_id: int, holdings: list) -> list[dict]:
    """
    Enrich holdings with current price + P&L.
    *holdings* comes from db.get_holdings(user_id).
    Returns list of dicts with extra fields: current_price, current_value,
    profit_loss, profit_loss_pct.
    """
    enriched = []
    for h in holdings:
        cur_price = fetch_current_price(h["symbol"])
        current_value = round(cur_price * h["total_shares"], 2) if cur_price else None
        pnl = round(current_value - h["total_invested"], 2) if current_value else None
        pnl_pct = round((pnl / h["total_invested"]) * 100, 2) if pnl and h["total_invested"] else None

        enriched.append({
            **h,
            "current_price": cur_price,
            "current_value": current_value,
            "profit_loss": pnl,
            "profit_loss_pct": pnl_pct,
        })
    return enriched
