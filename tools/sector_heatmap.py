"""
Tool 10: Sector Heatmap
Shows sector-wise performance with % change, color-coded heatmap in terminal.
Uses representative ETFs/stocks per sector for real data.
"""

import yfinance as yf
import numpy as np
from datetime import datetime


# Sector → representative tickers (mix of US ETFs + Indian sector leaders)
SECTORS = {
    "Technology": ["AAPL", "MSFT", "INFY.NS", "TCS.NS", "WIPRO.NS"],
    "Financial Services": ["JPM", "BAC", "HDFCBANK.NS", "SBIN.NS"],
    "Energy": ["XOM", "CVX", "RELIANCE.NS", "ONGC.NS"],
    "Healthcare": ["JNJ", "UNH", "SUNPHARMA.NS", "DRREDDY.NS"],
    "Consumer Cyclical": ["AMZN", "TSLA", "TITAN.NS", "TRENT.NS"],
    "Industrials": ["CAT", "HON", "LT.NS", "SIEMENS.NS"],
    "Communication": ["GOOGL", "META", "BHARTIARTL.NS"],
    "Consumer Defensive": ["PG", "KO", "HINDUNILVR.NS", "ITC.NS"],
    "Real Estate": ["AMT", "PLD", "DLF.NS", "GODREJPROP.NS"],
    "Utilities": ["NEE", "DUK", "NTPC.NS", "POWERGRID.NS"],
}


def _get_sector_change(tickers: list) -> dict:
    """Calculate avg % change for a sector from its representative tickers."""
    changes_1d = []
    changes_5d = []
    changes_1m = []
    ticker_data = []

    for sym in tickers:
        try:
            t = yf.Ticker(sym)
            hist = t.history(period="1mo")
            if hist.empty or len(hist) < 2:
                continue
            closes = hist["Close"].values
            c1d = (closes[-1] - closes[-2]) / closes[-2] * 100
            changes_1d.append(c1d)
            if len(closes) >= 6:
                changes_5d.append((closes[-1] - closes[-6]) / closes[-6] * 100)
            if len(closes) >= 20:
                changes_1m.append((closes[-1] - closes[-21]) / closes[-21] * 100)
            ticker_data.append({
                "symbol": sym,
                "price": round(float(closes[-1]), 2),
                "1d_change": round(c1d, 2),
            })
        except Exception:
            continue

    return {
        "avg_1d_change": round(float(np.mean(changes_1d)), 2) if changes_1d else 0,
        "avg_5d_change": round(float(np.mean(changes_5d)), 2) if changes_5d else 0,
        "avg_1m_change": round(float(np.mean(changes_1m)), 2) if changes_1m else 0,
        "tickers_tracked": len(ticker_data),
        "tickers": ticker_data,
    }


def get_sector_heatmap() -> dict:
    """
    Build a sector heatmap with 1-day, 5-day, and 1-month % changes.
    """
    print(f"\n  🔄 Building sector heatmap ({len(SECTORS)} sectors)...")
    sectors_result = {}

    for sector, tickers in SECTORS.items():
        print(f"     Scanning {sector}...", end=" ")
        data = _get_sector_change(tickers)
        sectors_result[sector] = data
        arrow = "▲" if data["avg_1d_change"] >= 0 else "▼"
        print(f"{arrow} {data['avg_1d_change']:+.2f}%")

    # Sort by 1D change
    sorted_sectors = sorted(sectors_result.items(), key=lambda x: x[1]["avg_1d_change"], reverse=True)

    return {
        "sectors": dict(sorted_sectors),
        "total_sectors": len(sorted_sectors),
        "best_sector": sorted_sectors[0][0] if sorted_sectors else "N/A",
        "worst_sector": sorted_sectors[-1][0] if sorted_sectors else "N/A",
        "market_sentiment": _calc_sentiment(sorted_sectors),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _calc_sentiment(sorted_sectors: list) -> dict:
    """Calculate overall market sentiment from sector data."""
    all_1d = [s[1]["avg_1d_change"] for s in sorted_sectors]
    all_5d = [s[1]["avg_5d_change"] for s in sorted_sectors]
    green_sectors = sum(1 for c in all_1d if c > 0)
    red_sectors = sum(1 for c in all_1d if c < 0)
    avg_1d = round(float(np.mean(all_1d)), 2) if all_1d else 0
    avg_5d = round(float(np.mean(all_5d)), 2) if all_5d else 0

    if avg_1d > 1:
        mood = "STRONG BULLISH"
    elif avg_1d > 0.2:
        mood = "BULLISH"
    elif avg_1d > -0.2:
        mood = "NEUTRAL"
    elif avg_1d > -1:
        mood = "BEARISH"
    else:
        mood = "STRONG BEARISH"

    return {
        "mood": mood,
        "avg_1d_all_sectors": avg_1d,
        "avg_5d_all_sectors": avg_5d,
        "green_sectors": green_sectors,
        "red_sectors": red_sectors,
    }


def display_sector_heatmap(data: dict):
    """Pretty-print the sector heatmap in terminal with color bars."""
    print(f"\n{'━' * 80}")
    print(f"  🗺️  SECTOR HEATMAP")
    print(f"{'━' * 80}")

    # Header
    print(f"  {'Sector':<22} {'1-Day':>8} {'5-Day':>8} {'1-Month':>8}  {'Heatbar':<20}")
    print(f"  {'─' * 72}")

    for sector, info in data["sectors"].items():
        d1 = info["avg_1d_change"]
        d5 = info["avg_5d_change"]
        d1m = info["avg_1m_change"]

        # Color: green for positive, red for negative
        if d1 > 1:
            bar = "🟩🟩🟩🟩🟩"
        elif d1 > 0.3:
            bar = "🟩🟩🟩⬜⬜"
        elif d1 > -0.3:
            bar = "⬜⬜🟨⬜⬜"
        elif d1 > -1:
            bar = "🟥🟥🟥⬜⬜"
        else:
            bar = "🟥🟥🟥🟥🟥"

        print(f"  {sector:<22} {d1:>+7.2f}% {d5:>+7.2f}% {d1m:>+7.2f}%  {bar}")

    # Summary
    sent = data["market_sentiment"]
    mood_emoji = {"STRONG BULLISH": "🟢🟢", "BULLISH": "🟢", "NEUTRAL": "🟡", "BEARISH": "🔴", "STRONG BEARISH": "🔴🔴"}
    print(f"  {'─' * 72}")
    print(f"\n  📊 Market Sentiment: {mood_emoji.get(sent['mood'], '⚪')} {sent['mood']}")
    print(f"     Avg 1D Change (all sectors) : {sent['avg_1d_all_sectors']:+.2f}%")
    print(f"     Avg 5D Change (all sectors) : {sent['avg_5d_all_sectors']:+.2f}%")
    print(f"     Green Sectors: {sent['green_sectors']}  |  Red Sectors: {sent['red_sectors']}")
    print(f"     Best : {data['best_sector']}  |  Worst : {data['worst_sector']}")
    print(f"{'━' * 80}")
