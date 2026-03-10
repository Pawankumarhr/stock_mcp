import yfinance as yf
import numpy as np
from datetime import datetime


def _compute_rsi(prices, period=14):
    """Compute RSI (Relative Strength Index)."""
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def _compute_sma(prices, period):
    """Simple Moving Average."""
    if len(prices) < period:
        return None
    return round(np.mean(prices[-period:]), 2)


def _compute_ema(prices, period):
    """Exponential Moving Average."""
    if len(prices) < period:
        return None
    multiplier = 2 / (period + 1)
    ema = prices[0]
    for p in prices[1:]:
        ema = (p - ema) * multiplier + ema
    return round(ema, 2)


def _compute_macd(prices):
    """MACD (12, 26, 9)."""
    if len(prices) < 26:
        return None, None, None
    ema12 = _compute_ema(prices, 12)
    ema26 = _compute_ema(prices, 26)
    macd_line = round(ema12 - ema26, 2)
    # Simplified signal line
    signal = _compute_ema(prices[-9:], 9) if len(prices) >= 9 else macd_line
    histogram = round(macd_line - (signal or 0), 2)
    return macd_line, signal, histogram


def _compute_bollinger(prices, period=20):
    """Bollinger Bands."""
    if len(prices) < period:
        return None, None, None
    sma = np.mean(prices[-period:])
    std = np.std(prices[-period:])
    return round(sma + 2 * std, 2), round(sma, 2), round(sma - 2 * std, 2)


def generate_signal(symbol: str, timeframe: str = "1mo") -> dict:
    """
    Generate a BUY / SELL / HOLD signal with confidence %.
    Uses RSI, SMA crossover, MACD, and Bollinger Bands.
    """
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period=timeframe)

    if hist.empty or len(hist) < 15:
        return {
            "symbol": symbol,
            "signal": "HOLD",
            "confidence": 0,
            "reason": "Insufficient data for analysis",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    closes = hist["Close"].values
    current_price = closes[-1]

    # ─── Indicators ───
    rsi = _compute_rsi(closes)
    sma_20 = _compute_sma(closes, 20)
    sma_50 = _compute_sma(closes, 50)
    ema_12 = _compute_ema(closes, 12)
    ema_26 = _compute_ema(closes, 26)
    macd_line, macd_signal, macd_hist = _compute_macd(closes)
    bb_upper, bb_mid, bb_lower = _compute_bollinger(closes)

    # ─── Scoring system (-100 to +100) ───
    score = 0
    reasons = []

    # RSI signal
    if rsi < 30:
        score += 25
        reasons.append(f"RSI={rsi} (oversold → bullish)")
    elif rsi > 70:
        score -= 25
        reasons.append(f"RSI={rsi} (overbought → bearish)")
    elif rsi < 45:
        score += 10
        reasons.append(f"RSI={rsi} (leaning bullish)")
    elif rsi > 55:
        score -= 10
        reasons.append(f"RSI={rsi} (leaning bearish)")
    else:
        reasons.append(f"RSI={rsi} (neutral)")

    # SMA crossover
    if sma_20 and sma_50:
        if sma_20 > sma_50:
            score += 20
            reasons.append(f"SMA20({sma_20}) > SMA50({sma_50}) → Golden cross (bullish)")
        else:
            score -= 20
            reasons.append(f"SMA20({sma_20}) < SMA50({sma_50}) → Death cross (bearish)")

    # Price vs SMA
    if sma_20:
        if current_price > sma_20:
            score += 10
            reasons.append(f"Price above SMA20 (bullish)")
        else:
            score -= 10
            reasons.append(f"Price below SMA20 (bearish)")

    # MACD
    if macd_line is not None and macd_signal is not None:
        if macd_line > macd_signal:
            score += 15
            reasons.append(f"MACD({macd_line}) > Signal({macd_signal}) → bullish")
        else:
            score -= 15
            reasons.append(f"MACD({macd_line}) < Signal({macd_signal}) → bearish")

    # Bollinger Bands
    if bb_lower and bb_upper:
        if current_price <= bb_lower:
            score += 20
            reasons.append(f"Price at lower Bollinger Band → oversold")
        elif current_price >= bb_upper:
            score -= 20
            reasons.append(f"Price at upper Bollinger Band → overbought")

    # ─── Determine signal ───
    if score >= 20:
        signal = "BUY"
    elif score <= -20:
        signal = "SELL"
    else:
        signal = "HOLD"

    confidence = min(abs(score), 100)

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "current_price": round(current_price, 2),
        "signal": signal,
        "confidence": confidence,
        "score": score,
        "indicators": {
            "rsi": rsi,
            "sma_20": sma_20,
            "sma_50": sma_50,
            "ema_12": ema_12,
            "ema_26": ema_26,
            "macd_line": macd_line,
            "macd_signal": macd_signal,
            "macd_histogram": macd_hist,
            "bollinger_upper": bb_upper,
            "bollinger_mid": bb_mid,
            "bollinger_lower": bb_lower,
        },
        "reasons": reasons,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def display_signal(sig: dict):
    """Pretty-print the trading signal."""
    emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡"}.get(sig["signal"], "⚪")
    bar = "█" * (sig["confidence"] // 5) + "░" * (20 - sig["confidence"] // 5)

    print(f"\n{'━' * 60}")
    print(f"  🤖 TRADING SIGNAL — {sig['symbol']} ({sig['timeframe']})")
    print(f"{'━' * 60}")
    print(f"  Current Price : {sig['current_price']}")
    print(f"  Signal        : {emoji} {sig['signal']}")
    print(f"  Confidence    : [{bar}] {sig['confidence']}%")
    print(f"  Score         : {sig['score']}")
    print(f"{'━' * 60}")
    print(f"  📊 Indicators:")
    ind = sig["indicators"]
    print(f"     RSI            : {ind['rsi']}")
    print(f"     SMA 20         : {ind['sma_20']}")
    print(f"     SMA 50         : {ind['sma_50']}")
    print(f"     EMA 12         : {ind['ema_12']}")
    print(f"     EMA 26         : {ind['ema_26']}")
    print(f"     MACD Line      : {ind['macd_line']}")
    print(f"     MACD Signal    : {ind['macd_signal']}")
    print(f"     MACD Histogram : {ind['macd_histogram']}")
    print(f"     Bollinger ↑    : {ind['bollinger_upper']}")
    print(f"     Bollinger Mid  : {ind['bollinger_mid']}")
    print(f"     Bollinger ↓    : {ind['bollinger_lower']}")
    print(f"{'━' * 60}")
    print(f"  📝 Reasoning:")
    for r in sig["reasons"]:
        print(f"     • {r}")
    print(f"{'━' * 60}")
