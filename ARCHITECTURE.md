# 🏗️ Architecture — Stock Analysis Platform

Developer guide to the codebase structure, data flow, and key design decisions.

---

## System Overview

```
┌─────────────────────────────────────────────────────┐
│                   STREAMLIT UI                       │
│  (streamlit_app.py — 11 pages, single-file app)     │
│                                                      │
│  Dashboard │ Live Stock │ Historical │ News │ Signal │
│  Options   │ Unusual    │ Scanner    │ Heatmap       │
│  Portfolio │ AI Chatbot                              │
└──────┬──────────────┬───────────────┬───────────────┘
       │              │               │
       ▼              ▼               ▼
┌──────────┐  ┌──────────────┐  ┌──────────────┐
│ tools/*  │  │ portfolio/*  │  │ OpenRouter   │
│ (7 modules)│ │ (SQLite DB)  │  │ GPT API      │
└──────┬───┘  └──────┬───────┘  └──────────────┘
       │             │
       ▼             ▼
┌──────────┐  ┌──────────────┐
│ yfinance │  │ portfolio.db │
│ (Yahoo)  │  │ (SQLite)     │
└──────────┘  └──────────────┘
```

---

## Key Components

### 1. Streamlit UI (`streamlit_app.py`)
- **Single-file app** with sidebar navigation routing to 11 pages
- Calls tool functions **directly** (no MCP subprocess) for speed
- AI Chatbot uses OpenRouter API with manual `TOOL_CALL` prompt engineering
- Session state manages chat history and portfolio user context

### 2. Tools (`tools/`)

| Module | Functions | Data Source |
|--------|-----------|-------------|
| `live_stock.py` | `fetch_stock_data()`, `fetch_historical_data()`, `fetch_options_data()` | yfinance |
| `news_fetch.py` | `fetch_news()` → NewsAPI + Google News scraping | NewsAPI, BeautifulSoup |
| `generating_signal.py` | `generate_signal()` → RSI, SMA, MACD, Bollinger Bands | yfinance |
| `cal_greek.py` | `build_contracts_from_chain()` → Black-Scholes from scratch | Pure math (no scipy) |
| `detect_unusual.py` | `detect_unusual_activity()` → volume/price/volatility alerts | yfinance |
| `scan_market.py` | `scan_market()` → scans all 10 companies with filters | yfinance |
| `sector_heatmap.py` | `get_sector_heatmap()` → 10 sectors, ~40 tickers | yfinance |
| `_cache.py` | `@ttl_cache`, `@retry_on_rate_limit`, `rate_limit()` | — |

### 3. Cache Layer (`tools/_cache.py`)
Yahoo Finance aggressively rate-limits cloud IPs. Three layers of protection:

```
@ttl_cache(300)              →  In-memory cache (5 min TTL)
@retry_on_rate_limit(3)      →  Exponential backoff on 429 errors
rate_limit()                  →  0.5s minimum gap between Yahoo calls
```

Cache TTLs: stock data=5min, historical=10min, options=15min, signals=10min, heatmap=15min.

### 4. Portfolio System (`portfolio/`)

```
portfolio/
├── db.py       →  SQLite schema (users + transactions tables)
│                  create_user, get_holdings, get_transactions, get_shares_owned
├── trading.py  →  fetch_price_on_date (yfinance), buy_stock, sell_stock
│                  portfolio_summary (enriches holdings with live prices)
└── menu.py     →  Terminal interactive menu (not used in Streamlit)
```

**Schema:**
```sql
users(id, username, created_at)
transactions(id, user_id, action[BUY/SELL], symbol, company_name,
             quantity, price_per_share, total_amount, transaction_date)
```

P&L is computed on-the-fly: `current_value - total_invested` using live yfinance prices.

### 5. MCP Server (`mcp_server.py`)
- Uses **FastMCP** with stdio transport
- Exposes all 13 tools (10 analysis + 3 portfolio)
- **Critical:** All imports are at top-level (lazy imports inside `@mcp.tool()` corrupt stdio protocol)
- Used by terminal `chatbot.py` only (Streamlit calls tools directly)

### 6. AI Chatbot — Two Implementations

| | Terminal (`chatbot.py`) | Streamlit (in `streamlit_app.py`) |
|---|----|-----|
| LLM | OpenRouter GPT-4.1-mini | Same |
| Tool execution | Via MCP subprocess | Direct function calls (TOOL_MAP dict) |
| Tool calling | `TOOL_CALL: {}` prompt pattern | Same pattern |
| Parsing | Brace-depth regex (handles nested JSON) | Same |
| System prompt | `role: "system"` (proper OpenAI format) | Same |

**Tool Call Flow:**
```
User query → LLM → "TOOL_CALL: {name, args}" → parse → execute → 
"TOOL_RESULT: ..." → LLM → final analysis → user
(loops up to 8 rounds)
```

---

## Deployment (Render)

```yaml
# render.yaml
services:
  - type: web
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: streamlit run streamlit_app.py --server.port 10000 --server.headless true --server.address 0.0.0.0
```

- Render injects `PORT=10000`
- `app.py` is an alternative entry point that launches Streamlit via subprocess
- Free tier — Yahoo rate-limiting mitigated by `_cache.py`

---

## API Keys Used

| Service | Purpose | Location |
|---------|---------|----------|
| OpenRouter | AI chatbot LLM | `chatbot.py`, `streamlit_app.py` |
| NewsAPI | Stock news | `tools/news_fetch.py` |

---

## Adding a New Tool

1. Create `tools/new_tool.py` with your function
2. Add `@ttl_cache` + `@retry_on_rate_limit` decorators if it calls yfinance
3. Register in `mcp_server.py` with `@mcp.tool()`
4. Add to `TOOL_MAP` dict in `streamlit_app.py` chatbot section
5. Add to `TOOL_DESCRIPTIONS` / `TOOL_PROMPT` in both chatbot files
6. Add a Streamlit page in `streamlit_app.py`
