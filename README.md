# 📈 Stock Analysis Platform

A full-stack stock analysis platform with **live market data**, **AI chatbot**, **portfolio simulator**, and **13 MCP tools** — built with Python, Streamlit, and OpenRouter GPT.

🔗 **Live Demo:** [stock-mcp-lfyg.onrender.com](https://stock-mcp-lfyg.onrender.com/)
📂 **GitHub:** [github.com/Pawankumarhr/stock_mcp](https://github.com/Pawankumarhr/stock_mcp)

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 📊 **Live Stock Data** | Real-time price, volume, market cap, PE, 52-week range for US & Indian stocks |
| 📅 **Historical Charts** | OHLCV charts with configurable time periods (1d to max) |
| 📰 **News Feed** | Latest headlines from NewsAPI + Google News |
| 🎯 **Trading Signals** | BUY/SELL/HOLD signals using RSI, SMA, MACD, Bollinger Bands |
| 🔗 **Options & Greeks** | Options chain + Black-Scholes Greeks (Delta, Gamma, Theta, Vega) |
| ⚡ **Unusual Activity** | Detects volume spikes, price gaps, volatility bursts |
| 🔍 **Market Scanner** | Scan all stocks by filters (oversold, bullish, near 52W low, etc.) |
| 🌡️ **Sector Heatmap** | Sector-wise performance with 1D/5D/1M changes |
| 💰 **Portfolio Simulator** | Buy/sell stocks on historical dates, track live P&L |
| 🤖 **AI Chatbot** | Natural language stock queries powered by GPT + live tools |

## 🏢 Supported Companies

| US Stocks | Indian Stocks (NSE) |
|-----------|-------------------|
| Apple (AAPL) | Reliance (RELIANCE.NS) |
| Google (GOOGL) | TCS (TCS.NS) |
| Microsoft (MSFT) | Infosys (INFY.NS) |
| Amazon (AMZN) | HDFC Bank (HDFCBANK.NS) |
| Tesla (TSLA) | Wipro (WIPRO.NS) |

## 🚀 Quick Start

```bash
# Clone
git clone https://github.com/Pawankumarhr/stock_mcp.git
cd stock_mcp

# Install dependencies
pip install -r requirements.txt

# Run the web UI
streamlit run streamlit_app.py
```

Open `http://localhost:8501` in your browser.

## 🛠️ Tech Stack

- **Frontend:** Streamlit
- **Data:** yfinance (Yahoo Finance API)
- **AI:** OpenRouter API (GPT-4.1-mini)
- **Database:** SQLite (portfolio)
- **MCP Server:** FastMCP (stdio protocol)
- **Deployment:** Render

## 📁 Project Structure

```
stock_mcp/
├── streamlit_app.py      # Streamlit web UI (all pages)
├── app.py                # Entry point (launches Streamlit)
├── chatbot.py            # Terminal AI chatbot (MCP + OpenRouter)
├── mcp_server.py         # MCP server exposing 13 tools
├── requirements.txt      # Python dependencies
├── render.yaml           # Render deployment config
├── tools/                # Stock analysis tool modules
│   ├── live_stock.py     # Live stock data + historical + options
│   ├── news_fetch.py     # NewsAPI + Google News
│   ├── generating_signal.py  # Trading signal generator
│   ├── cal_greek.py      # Black-Scholes options Greeks
│   ├── detect_unusual.py # Unusual activity detector
│   ├── scan_market.py    # Market scanner
│   ├── sector_heatmap.py # Sector performance heatmap
│   └── _cache.py         # Caching + rate-limit protection
├── portfolio/            # Portfolio simulator
│   ├── db.py             # SQLite database layer
│   ├── trading.py        # Buy/sell logic with price fetching
│   └── menu.py           # Terminal portfolio menu
└── ARCHITECTURE.md       # Developer documentation
```

## 📄 License

MIT