"""
Tool 8: Detect Unusual Activity
Analyzes a stock for volume spikes, price anomalies, and volatility bursts.
"""

import yfinance as yf
import numpy as np
from datetime import datetime
from tools._cache import ttl_cache, retry_on_rate_limit


@ttl_cache(ttl_seconds=600)
@retry_on_rate_limit(max_retries=3)
def detect_unusual_activity(symbol: str) -> dict:
    """
    Detect unusual trading activity for a given symbol.
    Checks: volume spikes, price gaps, volatility bursts, large candles, streak detection.
    """
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period="3mo")

    if hist.empty or len(hist) < 20:
        return {"symbol": symbol, "alerts": [], "anomalies": [], "message": "Insufficient data"}

    closes = hist["Close"].values
    volumes = hist["Volume"].values
    highs = hist["High"].values
    lows = hist["Low"].values
    opens = hist["Open"].values
    dates = [d.strftime("%Y-%m-%d") for d in hist.index]

    alerts = []
    anomalies = []

    # ─── 1. Volume Spike Detection ───
    vol_mean = np.mean(volumes[-20:])
    vol_std = np.std(volumes[-20:])
    for i in range(-5, 0):
        if vol_std > 0 and volumes[i] > vol_mean + 2 * vol_std:
            spike_ratio = round(volumes[i] / vol_mean, 2)
            alerts.append({
                "type": "VOLUME_SPIKE",
                "date": dates[i],
                "detail": f"Volume {int(volumes[i]):,} is {spike_ratio}x the 20-day avg ({int(vol_mean):,})",
                "severity": "HIGH" if spike_ratio > 3 else "MEDIUM",
                "value": int(volumes[i]),
                "threshold": int(vol_mean + 2 * vol_std),
            })

    # ─── 2. Price Gap Detection (gap up/down > 2%) ───
    for i in range(-5, 0):
        gap_pct = (opens[i] - closes[i - 1]) / closes[i - 1] * 100
        if abs(gap_pct) > 2.0:
            direction = "GAP_UP" if gap_pct > 0 else "GAP_DOWN"
            alerts.append({
                "type": direction,
                "date": dates[i],
                "detail": f"Price gapped {gap_pct:+.2f}% from prev close {closes[i-1]:.2f} to open {opens[i]:.2f}",
                "severity": "HIGH" if abs(gap_pct) > 4 else "MEDIUM",
                "gap_percent": round(gap_pct, 2),
            })

    # ─── 3. Volatility Burst (daily range > 2x avg range) ───
    daily_ranges = highs - lows
    avg_range = np.mean(daily_ranges[-20:])
    for i in range(-5, 0):
        if avg_range > 0 and daily_ranges[i] > 2 * avg_range:
            ratio = round(daily_ranges[i] / avg_range, 2)
            alerts.append({
                "type": "VOLATILITY_BURST",
                "date": dates[i],
                "detail": f"Daily range {daily_ranges[i]:.2f} is {ratio}x the 20-day avg range ({avg_range:.2f})",
                "severity": "HIGH" if ratio > 3 else "MEDIUM",
                "range": round(float(daily_ranges[i]), 2),
                "avg_range": round(float(avg_range), 2),
            })

    # ─── 4. Large Single-Day Move (> 3% in one day) ───
    for i in range(-5, 0):
        day_change = (closes[i] - closes[i - 1]) / closes[i - 1] * 100
        if abs(day_change) > 3.0:
            alerts.append({
                "type": "LARGE_MOVE",
                "date": dates[i],
                "detail": f"Price moved {day_change:+.2f}% in a single day ({closes[i-1]:.2f} → {closes[i]:.2f})",
                "severity": "HIGH" if abs(day_change) > 5 else "MEDIUM",
                "change_percent": round(day_change, 2),
            })

    # ─── 5. Consecutive Red/Green Days ───
    streak = 0
    streak_dir = None
    for i in range(-10, 0):
        change = closes[i] - closes[i - 1]
        if change > 0:
            if streak_dir == "up":
                streak += 1
            else:
                streak_dir = "up"
                streak = 1
        elif change < 0:
            if streak_dir == "down":
                streak += 1
            else:
                streak_dir = "down"
                streak = 1
    if streak >= 4:
        anomalies.append({
            "type": "STREAK",
            "detail": f"{streak} consecutive {'green' if streak_dir == 'up' else 'red'} days detected",
            "direction": streak_dir,
            "count": streak,
            "severity": "HIGH" if streak >= 6 else "MEDIUM",
        })

    # ─── 6. Price Near 52-Week Extremes ───
    info = ticker.info
    w52_high = info.get("fiftyTwoWeekHigh")
    w52_low = info.get("fiftyTwoWeekLow")
    current = closes[-1]
    if w52_high and current >= w52_high * 0.97:
        anomalies.append({
            "type": "NEAR_52W_HIGH",
            "detail": f"Price {current:.2f} is within 3% of 52-week high ({w52_high:.2f})",
            "proximity_pct": round((w52_high - current) / w52_high * 100, 2),
            "severity": "MEDIUM",
        })
    if w52_low and current <= w52_low * 1.03:
        anomalies.append({
            "type": "NEAR_52W_LOW",
            "detail": f"Price {current:.2f} is within 3% of 52-week low ({w52_low:.2f})",
            "proximity_pct": round((current - w52_low) / w52_low * 100, 2),
            "severity": "HIGH",
        })

    # ─── 7. Summary Stats ───
    recent_vol_avg = int(np.mean(volumes[-5:]))
    monthly_vol_avg = int(np.mean(volumes[-20:]))
    recent_volatility = round(float(np.std(closes[-5:]) / np.mean(closes[-5:]) * 100), 2)
    monthly_volatility = round(float(np.std(closes[-20:]) / np.mean(closes[-20:]) * 100), 2)

    return {
        "symbol": symbol,
        "current_price": round(float(current), 2),
        "analysis_period": "3 months",
        "alerts": alerts,
        "anomalies": anomalies,
        "total_alerts": len(alerts),
        "total_anomalies": len(anomalies),
        "stats": {
            "5d_avg_volume": recent_vol_avg,
            "20d_avg_volume": monthly_vol_avg,
            "volume_ratio": round(recent_vol_avg / monthly_vol_avg, 2) if monthly_vol_avg > 0 else 0,
            "5d_volatility_pct": recent_volatility,
            "20d_volatility_pct": monthly_volatility,
            "5d_return_pct": round(float((closes[-1] - closes[-6]) / closes[-6] * 100), 2),
            "20d_return_pct": round(float((closes[-1] - closes[-21]) / closes[-21] * 100), 2),
        },
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def display_unusual_activity(data: dict):
    """Pretty-print unusual activity report."""
    print(f"\n{'━' * 65}")
    print(f"  🔍 UNUSUAL ACTIVITY REPORT — {data['symbol']}")
    print(f"  Price: {data['current_price']}  |  Period: {data['analysis_period']}")
    print(f"{'━' * 65}")

    # Stats
    s = data["stats"]
    print(f"\n  📊 Key Stats:")
    print(f"     5D Avg Volume   : {s['5d_avg_volume']:,}")
    print(f"     20D Avg Volume  : {s['20d_avg_volume']:,}")
    print(f"     Volume Ratio    : {s['volume_ratio']}x")
    print(f"     5D Volatility   : {s['5d_volatility_pct']}%")
    print(f"     20D Volatility  : {s['20d_volatility_pct']}%")
    print(f"     5D Return       : {s['5d_return_pct']:+.2f}%")
    print(f"     20D Return      : {s['20d_return_pct']:+.2f}%")

    # Alerts
    if data["alerts"]:
        print(f"\n  🚨 Alerts ({data['total_alerts']}):")
        for a in data["alerts"]:
            sev = "🔴" if a["severity"] == "HIGH" else "🟡"
            print(f"     {sev} [{a['type']}] {a['date']}")
            print(f"        {a['detail']}")
    else:
        print(f"\n  ✅ No unusual alerts in the last 5 trading days.")

    # Anomalies
    if data["anomalies"]:
        print(f"\n  ⚠️  Anomalies ({data['total_anomalies']}):")
        for a in data["anomalies"]:
            sev = "🔴" if a["severity"] == "HIGH" else "🟡"
            print(f"     {sev} [{a['type']}] {a['detail']}")
    else:
        print(f"\n  ✅ No structural anomalies detected.")

    print(f"{'━' * 65}")
