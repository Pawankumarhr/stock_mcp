"""
Tool 9: Scan Market
Scans all tracked companies against filter criteria.
Returns matching symbols with key metrics.
"""

import yfinance as yf
import numpy as np
from datetime import datetime
from tools.live_stock import COMPANIES


FILTER_OPTIONS = {
    "1": "oversold",       # RSI < 30
    "2": "overbought",     # RSI > 70
    "3": "high_volume",    # Volume > 2x average
    "4": "bullish",        # Price > SMA20 and SMA20 > SMA50
    "5": "bearish",        # Price < SMA20 and SMA20 < SMA50
    "6": "near_52w_low",   # Within 5% of 52-week low
    "7": "near_52w_high",  # Within 5% of 52-week high
    "8": "all",            # Full scan — show all stocks with ranking
}


def _calc_rsi(prices, period=14):
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def _scan_single(symbol: str, name: str) -> dict:
    """Gather scan metrics for one stock."""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="3mo")
        if hist.empty or len(hist) < 20:
            return None
        info = ticker.info

        closes = hist["Close"].values
        volumes = hist["Volume"].values
        current = closes[-1]

        rsi = _calc_rsi(closes)
        sma20 = round(float(np.mean(closes[-20:])), 2)
        sma50 = round(float(np.mean(closes[-50:])), 2) if len(closes) >= 50 else None
        vol_avg = np.mean(volumes[-20:])
        vol_ratio = round(volumes[-1] / vol_avg, 2) if vol_avg > 0 else 0
        day_change = round(float((closes[-1] - closes[-2]) / closes[-2] * 100), 2)
        week_change = round(float((closes[-1] - closes[-6]) / closes[-6] * 100), 2) if len(closes) >= 6 else 0
        month_change = round(float((closes[-1] - closes[-21]) / closes[-21] * 100), 2) if len(closes) >= 21 else 0

        w52_high = info.get("fiftyTwoWeekHigh", 0)
        w52_low = info.get("fiftyTwoWeekLow", 0)
        from_52h = round((current - w52_high) / w52_high * 100, 2) if w52_high else 0
        from_52l = round((current - w52_low) / w52_low * 100, 2) if w52_low else 0

        pe = info.get("trailingPE", "N/A")
        mkt_cap = info.get("marketCap", 0)
        sector = info.get("sector", "N/A")

        return {
            "symbol": symbol,
            "name": name,
            "price": round(float(current), 2),
            "day_change_pct": day_change,
            "week_change_pct": week_change,
            "month_change_pct": month_change,
            "rsi": rsi,
            "sma20": sma20,
            "sma50": sma50,
            "above_sma20": current > sma20,
            "sma20_above_sma50": sma20 > sma50 if sma50 else None,
            "volume_ratio": vol_ratio,
            "52w_high": w52_high,
            "52w_low": w52_low,
            "from_52w_high_pct": from_52h,
            "from_52w_low_pct": from_52l,
            "pe_ratio": pe,
            "market_cap": mkt_cap,
            "sector": sector,
        }
    except Exception:
        return None


def scan_market(filter_criteria: str = "all") -> dict:
    """
    Scan all tracked companies and filter by criteria.
    Returns matching symbols with detailed metrics.
    """
    print(f"\n  🔄 Scanning {len(COMPANIES)} stocks...")
    results = []
    for key, (name, symbol) in COMPANIES.items():
        print(f"     Scanning {name} ({symbol})...", end=" ")
        data = _scan_single(symbol, name)
        if data:
            results.append(data)
            print(f"✓")
        else:
            print(f"✗ (no data)")

    # Apply filters
    matched = []
    for r in results:
        if filter_criteria == "oversold" and r["rsi"] < 30:
            matched.append(r)
        elif filter_criteria == "overbought" and r["rsi"] > 70:
            matched.append(r)
        elif filter_criteria == "high_volume" and r["volume_ratio"] > 2.0:
            matched.append(r)
        elif filter_criteria == "bullish" and r["above_sma20"] and r.get("sma20_above_sma50"):
            matched.append(r)
        elif filter_criteria == "bearish" and not r["above_sma20"] and r.get("sma20_above_sma50") is False:
            matched.append(r)
        elif filter_criteria == "near_52w_low" and r["from_52w_low_pct"] <= 5:
            matched.append(r)
        elif filter_criteria == "near_52w_high" and r["from_52w_high_pct"] >= -5:
            matched.append(r)
        elif filter_criteria == "all":
            matched.append(r)

    # Sort by day change (most interesting first)
    matched.sort(key=lambda x: abs(x["day_change_pct"]), reverse=True)

    return {
        "filter": filter_criteria,
        "total_scanned": len(results),
        "total_matched": len(matched),
        "matches": matched,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def display_filter_menu():
    """Show scan filter options."""
    print(f"\n  {'─' * 50}")
    print(f"  📡 Market Scanner — Choose Filter:")
    print(f"  {'─' * 50}")
    for k, v in FILTER_OPTIONS.items():
        labels = {
            "oversold": "Oversold (RSI < 30)",
            "overbought": "Overbought (RSI > 70)",
            "high_volume": "High Volume (> 2x avg)",
            "bullish": "Bullish (Price > SMA20 > SMA50)",
            "bearish": "Bearish (Price < SMA20 < SMA50)",
            "near_52w_low": "Near 52-Week Low (within 5%)",
            "near_52w_high": "Near 52-Week High (within 5%)",
            "all": "Full Scan (all stocks)",
        }
        print(f"  [{k}] {labels.get(v, v)}")
    print(f"  {'─' * 50}")


def display_scan_results(data: dict):
    """Pretty-print market scan results."""
    print(f"\n{'━' * 90}")
    print(f"  📡 MARKET SCAN — Filter: {data['filter'].upper()}  |  {data['total_matched']}/{data['total_scanned']} matched")
    print(f"{'━' * 90}")

    if not data["matches"]:
        print(f"  No stocks matched the filter '{data['filter']}'.")
        print(f"{'━' * 90}")
        return

    print(f"  {'Symbol':<16} {'Price':>8} {'Day%':>7} {'Week%':>7} {'Mon%':>7} {'RSI':>6} {'VolR':>6} {'From52H':>8} {'From52L':>8}")
    print(f"  {'─' * 85}")
    for r in data["matches"]:
        sym = f"{r['name'][:12]}"
        d_col = "\033[92m" if r["day_change_pct"] > 0 else "\033[91m" if r["day_change_pct"] < 0 else ""
        rst = "\033[0m"
        print(
            f"  {sym:<16} {r['price']:>8.2f} "
            f"{d_col}{r['day_change_pct']:>+6.2f}%{rst} "
            f"{r['week_change_pct']:>+6.2f}% "
            f"{r['month_change_pct']:>+6.2f}% "
            f"{r['rsi']:>6.1f} "
            f"{r['volume_ratio']:>5.1f}x "
            f"{r['from_52w_high_pct']:>+7.1f}% "
            f"{r['from_52w_low_pct']:>+7.1f}%"
        )

    print(f"  {'─' * 85}")

    # Analysis summary
    avg_rsi = np.mean([r["rsi"] for r in data["matches"]])
    avg_day = np.mean([r["day_change_pct"] for r in data["matches"]])
    bullish_count = sum(1 for r in data["matches"] if r["above_sma20"])
    bearish_count = len(data["matches"]) - bullish_count

    print(f"\n  📊 Scan Summary:")
    print(f"     Avg RSI         : {avg_rsi:.1f}")
    print(f"     Avg Day Change  : {avg_day:+.2f}%")
    print(f"     Bullish (>SMA20): {bullish_count}  |  Bearish (<SMA20): {bearish_count}")
    print(f"{'━' * 90}")
