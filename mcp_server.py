"""
Stock Analysis MCP Server
Exposes 10 stock-market tools via the Model Context Protocol (stdio transport).
Any MCP-compatible client (Claude Desktop, VS Code, custom chatbot) can use these.
"""

import json, sys, os, io, contextlib, re, warnings

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Pre-load ALL tool imports BEFORE MCP starts listening on stdio ────────
# yfinance / requests / numpy print warnings on first import.
# If these go to stdout/stderr after MCP starts, they corrupt the protocol.
_buf = io.StringIO()
_err = io.StringIO()
with contextlib.redirect_stdout(_buf), contextlib.redirect_stderr(_err), \
     warnings.catch_warnings():
    warnings.simplefilter("ignore")
    from tools.live_stock import (
        COMPANIES, fetch_stock_data as _fetch_stock_data,
        fetch_historical_data as _fetch_historical_data,
        fetch_options_data as _fetch_options_data,
    )
    from tools.news_fetch import fetch_news as _fetch_news
    from tools.generating_signal import generate_signal as _generate_signal
    from tools.cal_greek import build_contracts_from_chain as _build_contracts
    from tools.detect_unusual import detect_unusual_activity as _detect_unusual
    from tools.scan_market import scan_market as _scan_market
    from tools.sector_heatmap import get_sector_heatmap as _get_heatmap
    from portfolio.db import (
        list_users as _list_users,
        get_holdings as _get_holdings,
        get_transactions as _get_transactions,
    )
    from portfolio.trading import portfolio_summary as _portfolio_summary
del _buf, _err

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Stock Analysis Server")


# ── helpers ──────────────────────────────────────────────────────────────
def _safe_json(data):
    """Full-precision JSON (no scientific notation)."""
    raw = json.dumps(data, indent=2, default=str)
    def _expand(m):
        return f"{float(m.group()):.10f}".rstrip("0").rstrip(".")
    return re.sub(r"-?\d+\.\d+e[+-]?\d+", _expand, raw)


def _quiet(fn, *args, **kwargs):
    """Run *fn* while capturing any print() and stderr output (keeps MCP stdio clean)."""
    buf = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err), \
         warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return fn(*args, **kwargs)


# ── Tool 0 ───────────────────────────────────────────────────────────────
@mcp.tool()
def list_companies() -> str:
    """List every tracked company with its ticker symbol.
    Returns JSON mapping symbol → company name.
    Available: AAPL, GOOGL, MSFT, AMZN, TSLA (US) and
    RELIANCE.NS, TCS.NS, INFY.NS, HDFCBANK.NS, WIPRO.NS (India NSE)."""
    return _safe_json({v[1]: v[0] for _, v in COMPANIES.items()})


# ── Tool 1 ───────────────────────────────────────────────────────────────
@mcp.tool()
def get_stock_data(symbol: str) -> str:
    """Get live stock data — price, open, high, low, volume, market cap,
    PE ratio, dividend yield, beta, 52-week range, sector, industry.
    Use .NS suffix for Indian NSE stocks (e.g. RELIANCE.NS)."""
    return _safe_json(_quiet(_fetch_stock_data, symbol))


# ── Tool 2 ───────────────────────────────────────────────────────────────
@mcp.tool()
def get_historical_data(symbol: str, period: str = "1mo") -> str:
    """Historical OHLCV data.  period: 1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,ytd,max."""
    return _safe_json(_quiet(_fetch_historical_data, symbol, period))


# ── Tool 3 ───────────────────────────────────────────────────────────────
@mcp.tool()
def get_options_chain(symbol: str) -> str:
    """Options chain (calls & puts) for a stock.
    Indian stocks use ADR mapping where available
    (HDFCBANK.NS→HDB, INFY.NS→INFY, WIPRO.NS→WIT)."""
    return _safe_json(_quiet(_fetch_options_data, symbol))


# ── Tool 4 ───────────────────────────────────────────────────────────────
@mcp.tool()
def calculate_greeks(symbol: str) -> str:
    """Options Greeks (Delta, Gamma, Theta, Vega) via pure Black-Scholes.
    Fetches live price + options chain, then computes Greeks for each contract."""
    stock = _quiet(_fetch_stock_data, symbol)
    opts  = _quiet(_fetch_options_data, symbol)
    spot  = stock.get("price", 0)
    if spot and opts.get("available"):
        greeks = _quiet(_build_contracts, spot, opts)
        return _safe_json(greeks)
    return json.dumps({"error": "Options data not available for Greeks calculation."})


# ── Tool 5 ───────────────────────────────────────────────────────────────
@mcp.tool()
def get_news(company_name: str, symbol: str) -> str:
    """Latest news from NewsAPI + Google News RSS.
    company_name: e.g. 'Wipro'  symbol: e.g. 'WIPRO.NS'."""
    return _safe_json(_quiet(_fetch_news, company_name, symbol))


# ── Tool 6 ───────────────────────────────────────────────────────────────
@mcp.tool()
def generate_trading_signal(symbol: str) -> str:
    """BUY / SELL / HOLD signal with confidence %.
    Uses RSI, SMA, EMA, MACD, Bollinger Bands (3-month data)."""
    return _safe_json(_quiet(_generate_signal, symbol, timeframe="3mo"))


# ── Tool 7 ───────────────────────────────────────────────────────────────
@mcp.tool()
def detect_unusual_activity(symbol: str) -> str:
    """Detect volume spikes, price gaps, volatility bursts, streaks,
    proximity to 52-week extremes."""
    return _safe_json(_quiet(_detect_unusual, symbol))


# ── Tool 8 ───────────────────────────────────────────────────────────────
@mcp.tool()
def scan_market(filter_criteria: str = "all") -> str:
    """Scan all tracked companies against a filter.
    Filters: oversold, overbought, high_volume, bullish, bearish,
    near_52w_low, near_52w_high, all."""
    return _safe_json(_quiet(_scan_market, filter_criteria))


# ── Tool 9 ───────────────────────────────────────────────────────────────
@mcp.tool()
def get_sector_heatmap() -> str:
    """Sector-wise performance heatmap with 1-day, 5-day, 1-month % changes.
    Covers Tech, Finance, Energy, Healthcare, Consumer, Industrials, etc."""
    return _safe_json(_quiet(_get_heatmap))


# ── Tool 10 ──────────────────────────────────────────────────────────────
@mcp.tool()
def list_portfolio_users() -> str:
    """List all registered portfolio users.  Returns JSON array of
    {id, username, created_at}.  Use the 'id' to query a user's holdings."""
    return _safe_json(_quiet(_list_users))


# ── Tool 11 ──────────────────────────────────────────────────────────────
@mcp.tool()
def get_portfolio_summary(user_id: int) -> str:
    """Get a user's portfolio with LIVE P&L.  For each holding returns:
    symbol, company_name, total_shares, avg_buy_price, total_invested,
    current_price, current_value, profit_loss, profit_loss_pct.
    Also includes overall totals.  Pass the numeric user_id."""
    holdings = _quiet(_get_holdings, user_id)
    if not holdings:
        return json.dumps({"message": "This user has no holdings yet."})
    enriched = _quiet(_portfolio_summary, user_id, holdings)
    total_inv = sum(h["total_invested"] for h in enriched)
    total_val = sum(h["current_value"] or 0 for h in enriched)
    total_pnl = round(total_val - total_inv, 2)
    pnl_pct   = round((total_pnl / total_inv) * 100, 2) if total_inv else 0
    return _safe_json({
        "user_id": user_id,
        "holdings": enriched,
        "totals": {
            "total_invested": round(total_inv, 2),
            "current_value": round(total_val, 2),
            "net_profit_loss": total_pnl,
            "profit_loss_pct": pnl_pct,
        },
    })


# ── Tool 12 ──────────────────────────────────────────────────────────────
@mcp.tool()
def get_transaction_history(user_id: int, symbol: str = "") -> str:
    """Get transaction history for a user.  Optionally filter by symbol.
    Returns list of {id, action, symbol, company_name, quantity,
    price_per_share, total_amount, transaction_date}."""
    sym = symbol if symbol else None
    txns = _quiet(_get_transactions, user_id, sym)
    return _safe_json(txns)


# ── entry point ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    mcp.run()          # defaults to stdio transport
