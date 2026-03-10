import yfinance as yf
from datetime import datetime


COMPANIES = {
    # --- US Companies ---
    "1": ("Apple", "AAPL"),
    "2": ("Google", "GOOGL"),
    "3": ("Microsoft", "MSFT"),
    "4": ("Amazon", "AMZN"),
    "5": ("Tesla", "TSLA"),
    # --- Indian Companies (NSE) ---
    "6": ("Reliance Industries", "RELIANCE.NS"),
    "7": ("Tata Consultancy Services", "TCS.NS"),
    "8": ("Infosys", "INFY.NS"),
    "9": ("HDFC Bank", "HDFCBANK.NS"),
    "10": ("Wipro", "WIPRO.NS"),
}


def display_menu():
    """Display the company selection menu."""
    print("\n" + "=" * 55)
    print("        📈 LIVE STOCK DATA FETCHER 📈")
    print("=" * 55)
    print("  ── US Companies ──")
    for key in ["1", "2", "3", "4", "5"]:
        name, symbol = COMPANIES[key]
        print(f"  [{key:>2}] {name} ({symbol})")
    print("  ── Indian Companies (NSE) ──")
    for key in ["6", "7", "8", "9", "10"]:
        name, symbol = COMPANIES[key]
        print(f"  [{key:>2}] {name} ({symbol})")
    print(f"  [ 0] Exit")
    print("=" * 55)


def fetch_stock_data(symbol: str) -> dict:
    """Fetch live NSE/BSE/US stock data using yfinance."""
    ticker = yf.Ticker(symbol)
    info = ticker.info

    return {
        "symbol": symbol,
        "name": info.get("shortName", "N/A"),
        "exchange": info.get("exchange", "N/A"),
        "currency": info.get("currency", "N/A"),
        "price": info.get("currentPrice") or info.get("regularMarketPrice", "N/A"),
        "open": info.get("regularMarketOpen", "N/A"),
        "high": info.get("regularMarketDayHigh", "N/A"),
        "low": info.get("regularMarketDayLow", "N/A"),
        "prev_close": info.get("regularMarketPreviousClose", "N/A"),
        "volume": info.get("regularMarketVolume", "N/A"),
        "market_cap": info.get("marketCap", "N/A"),
        "52w_high": info.get("fiftyTwoWeekHigh", "N/A"),
        "52w_low": info.get("fiftyTwoWeekLow", "N/A"),
        "pe_ratio": info.get("trailingPE", "N/A"),
        "dividend_yield": info.get("dividendYield", "N/A"),
        "beta": info.get("beta", "N/A"),
        "sector": info.get("sector", "N/A"),
        "industry": info.get("industry", "N/A"),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def fetch_historical_data(symbol: str, period: str = "1mo") -> list:
    """Fetch historical OHLC data using yfinance."""
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period=period)
    records = []
    for date, row in hist.iterrows():
        records.append({
            "date": date.strftime("%Y-%m-%d"),
            "open": round(row["Open"], 2),
            "high": round(row["High"], 2),
            "low": round(row["Low"], 2),
            "close": round(row["Close"], 2),
            "volume": int(row["Volume"]),
        })
    return records


def fetch_options_data(symbol: str) -> dict:
    """Fetch options chain data. Uses US ADR for Indian .NS stocks (Yahoo has no NSE options)."""
    ADR_MAP = {
        "RELIANCE.NS": None,
        "TCS.NS": None,
        "INFY.NS": "INFY",
        "HDFCBANK.NS": "HDB",
        "WIPRO.NS": "WIT",
    }

    lookup = symbol
    note = None
    if symbol in ADR_MAP:
        adr = ADR_MAP[symbol]
        if adr:
            lookup = adr
            note = f"Options via US ADR ({adr}) — NSE options not on Yahoo Finance"
        else:
            return {"available": False, "message": f"No options for {symbol} (no US ADR). Use NSE/BSE broker for Indian F&O."}

    ticker = yf.Ticker(lookup)
    try:
        expirations = ticker.options
        if not expirations:
            return {"available": False, "message": f"No options expirations for {lookup}"}
        nearest = expirations[0]
        chain = ticker.option_chain(nearest)
        calls_df = chain.calls.head(5)[["strike", "lastPrice", "volume", "openInterest", "impliedVolatility"]]
        puts_df = chain.puts.head(5)[["strike", "lastPrice", "volume", "openInterest", "impliedVolatility"]]
        calls = calls_df.fillna(0).to_dict("records")
        puts = puts_df.fillna(0).to_dict("records")
        result = {
            "available": True,
            "expiration": nearest,
            "symbol": lookup,
            "top_calls": calls,
            "top_puts": puts,
        }
        if note:
            result["note"] = note
        return result
    except Exception as e:
        return {"available": False, "message": f"Options error for {lookup}: {e}"}


def format_number(num, currency="$"):
    """Format large numbers for readability."""
    if isinstance(num, (int, float)):
        if num >= 1_000_000_000_000:
            return f"{currency}{num / 1_000_000_000_000:.2f}T"
        if num >= 1_000_000_000:
            return f"{currency}{num / 1_000_000_000:.2f}B"
        if num >= 1_000_000:
            return f"{currency}{num / 1_000_000:.2f}M"
        return f"{currency}{num:,.2f}"
    return str(num)


def display_stock_data(data: dict):
    """Pretty-print stock data in the terminal."""
    cur = "₹" if data.get("currency") == "INR" else "$"
    print(f"\n{'─' * 55}")
    print(f"  {data['name']} ({data['symbol']})")
    print(f"  Exchange: {data['exchange']}  |  Currency: {data['currency']}")
    print(f"  Sector: {data['sector']}  |  Industry: {data['industry']}")
    print(f"  Fetched at: {data['timestamp']}")
    print(f"{'─' * 55}")
    print(f"  💰 Current Price : {cur}{data['price']}")
    print(f"  📂 Open          : {cur}{data['open']}")
    print(f"  🔺 Day High      : {cur}{data['high']}")
    print(f"  🔻 Day Low       : {cur}{data['low']}")
    print(f"  📊 Prev Close    : {cur}{data['prev_close']}")
    vol = f"{data['volume']:,}" if isinstance(data['volume'], (int, float)) else data['volume']
    print(f"  📦 Volume        : {vol}")
    print(f"  🏦 Market Cap    : {format_number(data['market_cap'], cur)}")
    print(f"  📈 52W High      : {cur}{data['52w_high']}")
    print(f"  📉 52W Low       : {cur}{data['52w_low']}")
    print(f"  📋 P/E Ratio     : {data['pe_ratio']}")
    div = f"{data['dividend_yield']*100:.2f}%" if isinstance(data['dividend_yield'], (int, float)) else "N/A"
    print(f"  💎 Dividend Yield: {div}")
    print(f"  📐 Beta          : {data['beta']}")
    print(f"{'─' * 55}")


def display_historical(records: list):
    """Print last 5 days of historical OHLC."""
    print(f"\n  📅 Recent Historical OHLC (last 5 days):")
    print(f"  {'Date':<12} {'Open':>10} {'High':>10} {'Low':>10} {'Close':>10} {'Volume':>12}")
    print(f"  {'─'*66}")
    for r in records[-5:]:
        print(f"  {r['date']:<12} {r['open']:>10.2f} {r['high']:>10.2f} {r['low']:>10.2f} {r['close']:>10.2f} {r['volume']:>12,}")


def display_options(opts: dict):
    """Print options chain summary."""
    if not opts.get("available"):
        print(f"\n  ⚠️  {opts.get('message', 'No options data')}")
        return
    if opts.get("note"):
        print(f"\n  ℹ️  {opts['note']}")
    print(f"\n  🔗 Options Chain — {opts.get('symbol', '')} (Expiry: {opts['expiration']})")
    print(f"  ── Top 5 CALLS ──")
    print(f"  {'Strike':>10} {'Last':>8} {'Vol':>8} {'OI':>8} {'IV':>8}")
    for c in opts["top_calls"]:
        print(f"  {c['strike']:>10.2f} {c['lastPrice']:>8.2f} {str(c.get('volume','N/A')):>8} {c['openInterest']:>8} {c['impliedVolatility']:>8.2%}")
    print(f"  ── Top 5 PUTS ──")
    print(f"  {'Strike':>10} {'Last':>8} {'Vol':>8} {'OI':>8} {'IV':>8}")
    for p in opts["top_puts"]:
        print(f"  {p['strike']:>10.2f} {p['lastPrice']:>8.2f} {str(p.get('volume','N/A')):>8} {p['openInterest']:>8} {p['impliedVolatility']:>8.2%}")
