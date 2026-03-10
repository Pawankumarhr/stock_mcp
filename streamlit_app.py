"""
Streamlit UI for Stock Analysis Platform
─────────────────────────────────────────
Run:  streamlit run streamlit_app.py
"""

import streamlit as st
import pandas as pd
import json, sys, os, time
from datetime import datetime, date

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tools.live_stock import COMPANIES, fetch_stock_data, fetch_historical_data, fetch_options_data
from tools.news_fetch import fetch_news
from tools.generating_signal import generate_signal
from tools.cal_greek import build_contracts_from_chain
from tools.detect_unusual import detect_unusual_activity
from tools.scan_market import scan_market, FILTER_OPTIONS
from tools.sector_heatmap import get_sector_heatmap
from portfolio.db import (
    init_db, create_user, list_users, get_user,
    get_holdings, get_transactions, get_shares_owned,
)
from portfolio.trading import buy_stock, sell_stock, portfolio_summary

init_db()

# ── page config ──────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Stock Analysis Platform",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── company helper ───────────────────────────────────────────────────────
COMPANY_LIST = {v[1]: v[0] for v in COMPANIES.values()}   # symbol → name
COMPANY_OPTIONS = [f"{name} ({sym})" for sym, name in COMPANY_LIST.items()]

def _parse_company(option: str):
    """Extract (name, symbol) from 'Apple (AAPL)' style string."""
    sym = option.split("(")[-1].rstrip(")")
    return COMPANY_LIST[sym], sym

def _currency(symbol: str) -> str:
    return "₹" if ".NS" in symbol else "$"

# ── sidebar nav ──────────────────────────────────────────────────────────
st.sidebar.title("📈 Stock Platform")
page = st.sidebar.radio(
    "Navigate",
    [
        "🏠 Dashboard",
        "📊 Live Stock Data",
        "📅 Historical Data",
        "📰 News",
        "🎯 Trading Signal",
        "🔗 Options & Greeks",
        "⚡ Unusual Activity",
        "🔍 Market Scanner",
        "🌡️ Sector Heatmap",
        "💰 Portfolio",
        "🤖 AI Chatbot",
    ],
)


# ════════════════════════════════════════════════════════════════════════
# PAGE: Dashboard
# ════════════════════════════════════════════════════════════════════════
if page == "🏠 Dashboard":
    st.title("📈 Stock Analysis Platform")
    st.markdown("Welcome! Use the **sidebar** to navigate between features.")

    col1, col2, col3 = st.columns(3)
    col1.metric("Tracked Companies", len(COMPANIES))
    col2.metric("US Stocks", 5)
    col3.metric("Indian NSE Stocks", 5)

    st.markdown("---")
    st.subheader("Available Features")
    features = {
        "📊 Live Stock Data": "Real-time price, volume, market cap, PE ratio, sector info",
        "📅 Historical Data": "OHLCV candle data for any period (1d to max)",
        "📰 News": "Latest news from NewsAPI + Google News RSS",
        "🎯 Trading Signal": "BUY / SELL / HOLD with confidence % (RSI, MACD, Bollinger)",
        "🔗 Options & Greeks": "Options chain + Black-Scholes Greeks (Delta, Gamma, Theta, Vega)",
        "⚡ Unusual Activity": "Volume spikes, price gaps, volatility bursts, 52-week proximity",
        "🔍 Market Scanner": "Scan all companies with filters (oversold, bullish, etc.)",
        "🌡️ Sector Heatmap": "Sector performance — 1-day, 5-day, 1-month % changes",
        "💰 Portfolio": "Buy/sell stocks at historical prices, track P&L with SQLite",
        "🤖 AI Chatbot": "Natural language queries powered by Claude AI + live tools",
    }
    for feat, desc in features.items():
        st.markdown(f"**{feat}** — {desc}")

    st.markdown("---")
    st.subheader("Quick Company List")
    df = pd.DataFrame(
        [(k, v[0], v[1]) for k, v in COMPANIES.items()],
        columns=["#", "Company", "Symbol"],
    )
    st.dataframe(df, width='stretch', hide_index=True)


# ════════════════════════════════════════════════════════════════════════
# PAGE: Live Stock Data
# ════════════════════════════════════════════════════════════════════════
elif page == "📊 Live Stock Data":
    st.title("📊 Live Stock Data")
    selected = st.selectbox("Select Company", COMPANY_OPTIONS)
    name, symbol = _parse_company(selected)
    cur = _currency(symbol)

    if st.button("Fetch Live Data", type="primary"):
        with st.spinner(f"Fetching {symbol}..."):
            data = fetch_stock_data(symbol)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Price", f"{cur}{data['price']}")
        col2.metric("Open", f"{cur}{data['open']}")
        col3.metric("Day High", f"{cur}{data['high']}")
        col4.metric("Day Low", f"{cur}{data['low']}")

        col5, col6, col7, col8 = st.columns(4)
        vol = f"{data['volume']:,}" if isinstance(data['volume'], (int, float)) else data['volume']
        col5.metric("Volume", vol)
        mcap = data['market_cap']
        if isinstance(mcap, (int, float)):
            if mcap >= 1e12:
                mcap_str = f"{cur}{mcap/1e12:.2f}T"
            elif mcap >= 1e9:
                mcap_str = f"{cur}{mcap/1e9:.2f}B"
            else:
                mcap_str = f"{cur}{mcap/1e6:.2f}M"
        else:
            mcap_str = str(mcap)
        col6.metric("Market Cap", mcap_str)
        col7.metric("PE Ratio", data.get('pe_ratio', 'N/A'))
        div = f"{data['dividend_yield']*100:.2f}%" if isinstance(data.get('dividend_yield'), (int, float)) else "N/A"
        col8.metric("Dividend Yield", div)

        col9, col10, col11, col12 = st.columns(4)
        col9.metric("52W High", f"{cur}{data['52w_high']}")
        col10.metric("52W Low", f"{cur}{data['52w_low']}")
        col11.metric("Beta", data.get('beta', 'N/A'))
        col12.metric("Prev Close", f"{cur}{data['prev_close']}")

        st.info(f"**Sector:** {data.get('sector','N/A')} · **Industry:** {data.get('industry','N/A')} · Fetched: {data['timestamp']}")

        with st.expander("Raw JSON"):
            st.json(data)


# ════════════════════════════════════════════════════════════════════════
# PAGE: Historical Data
# ════════════════════════════════════════════════════════════════════════
elif page == "📅 Historical Data":
    st.title("📅 Historical OHLCV Data")
    selected = st.selectbox("Select Company", COMPANY_OPTIONS)
    name, symbol = _parse_company(selected)
    period = st.select_slider(
        "Period",
        options=["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"],
        value="1mo",
    )

    if st.button("Fetch Historical Data", type="primary"):
        with st.spinner(f"Fetching {symbol} history ({period})..."):
            records = fetch_historical_data(symbol, period)

        if records:
            df = pd.DataFrame(records)
            df["date"] = pd.to_datetime(df["date"])

            st.subheader("Price Chart")
            st.line_chart(df.set_index("date")[["close", "open", "high", "low"]])

            st.subheader("Volume Chart")
            st.bar_chart(df.set_index("date")["volume"])

            st.subheader("Data Table")
            st.dataframe(df, width='stretch', hide_index=True)
        else:
            st.warning("No data returned.")


# ════════════════════════════════════════════════════════════════════════
# PAGE: News
# ════════════════════════════════════════════════════════════════════════
elif page == "📰 News":
    st.title("📰 Stock News")
    selected = st.selectbox("Select Company", COMPANY_OPTIONS)
    name, symbol = _parse_company(selected)

    if st.button("Fetch News", type="primary"):
        with st.spinner(f"Fetching news for {name}..."):
            news = fetch_news(name, symbol)

        for source_key in ["newsapi", "google_news"]:
            articles = news.get(source_key, [])
            if articles:
                src_label = "NewsAPI" if source_key == "newsapi" else "Google News"
                st.subheader(f"{src_label} ({len(articles)} articles)")
                for art in articles:
                    title = art.get("title", "No title")
                    link = art.get("url") or art.get("link", "#")
                    pub = art.get("published") or art.get("publishedAt", "")
                    st.markdown(f"- [{title}]({link})  \n  *{pub}*")

        with st.expander("Raw JSON"):
            st.json(news)


# ════════════════════════════════════════════════════════════════════════
# PAGE: Trading Signal
# ════════════════════════════════════════════════════════════════════════
elif page == "🎯 Trading Signal":
    st.title("🎯 Trading Signal Generator")
    selected = st.selectbox("Select Company", COMPANY_OPTIONS)
    name, symbol = _parse_company(selected)

    if st.button("Generate Signal", type="primary"):
        with st.spinner(f"Analyzing {symbol}..."):
            sig = generate_signal(symbol, timeframe="3mo")

        signal = sig.get("signal", "N/A")
        confidence = sig.get("confidence", 0)

        color = "green" if signal == "BUY" else ("red" if signal == "SELL" else "orange")
        st.markdown(f"### Signal: :{color}[**{signal}**]  —  Confidence: **{confidence}%**")

        indicators = sig.get("indicators", {})
        if indicators:
            st.subheader("Indicators")
            ind_cols = st.columns(3)
            i = 0
            for k, v in indicators.items():
                ind_cols[i % 3].metric(k.upper(), f"{v:.2f}" if isinstance(v, float) else str(v))
                i += 1

        reasoning = sig.get("reasoning", [])
        if reasoning:
            st.subheader("Reasoning")
            for r in reasoning:
                st.markdown(f"- {r}")

        with st.expander("Raw JSON"):
            st.json(sig)


# ════════════════════════════════════════════════════════════════════════
# PAGE: Options & Greeks
# ════════════════════════════════════════════════════════════════════════
elif page == "🔗 Options & Greeks":
    st.title("🔗 Options Chain & Greeks")
    selected = st.selectbox("Select Company", COMPANY_OPTIONS)
    name, symbol = _parse_company(selected)

    if st.button("Fetch Options + Greeks", type="primary"):
        with st.spinner(f"Fetching options for {symbol}..."):
            stock = fetch_stock_data(symbol)
            opts = fetch_options_data(symbol)

        if not opts.get("available"):
            st.warning(opts.get("message", "Options data not available."))
        else:
            if opts.get("note"):
                st.info(opts["note"])
            st.subheader(f"Expiration: {opts['expiration']}")

            tab_calls, tab_puts = st.tabs(["📈 Calls", "📉 Puts"])
            with tab_calls:
                if opts.get("top_calls"):
                    st.dataframe(pd.DataFrame(opts["top_calls"]), width='stretch', hide_index=True)
            with tab_puts:
                if opts.get("top_puts"):
                    st.dataframe(pd.DataFrame(opts["top_puts"]), width='stretch', hide_index=True)

            # Greeks
            spot = stock.get("price", 0)
            if spot and opts.get("available"):
                with st.spinner("Computing Black-Scholes Greeks..."):
                    greeks = build_contracts_from_chain(spot, opts)
                if greeks:
                    st.subheader("Options Greeks (Black-Scholes)")
                    gdf = pd.DataFrame(greeks)
                    st.dataframe(gdf, width='stretch', hide_index=True)


# ════════════════════════════════════════════════════════════════════════
# PAGE: Unusual Activity
# ════════════════════════════════════════════════════════════════════════
elif page == "⚡ Unusual Activity":
    st.title("⚡ Unusual Activity Detector")
    selected = st.selectbox("Select Company", COMPANY_OPTIONS)
    name, symbol = _parse_company(selected)

    if st.button("Detect", type="primary"):
        with st.spinner(f"Scanning {symbol}..."):
            result = detect_unusual_activity(symbol)

        alerts = result.get("alerts", [])
        if alerts:
            st.subheader(f"🚨 {len(alerts)} Alert(s) Found")
            for a in alerts:
                severity = a.get("severity", "info")
                icon = "🔴" if severity == "high" else ("🟡" if severity == "medium" else "🟢")
                st.markdown(f"{icon} **{a.get('type', '')}** — {a.get('description', '')}")
        else:
            st.success("No unusual activity detected.")

        with st.expander("Full Details"):
            st.json(result)


# ════════════════════════════════════════════════════════════════════════
# PAGE: Market Scanner
# ════════════════════════════════════════════════════════════════════════
elif page == "🔍 Market Scanner":
    st.title("🔍 Market Scanner")
    filter_labels = {
        "all": "All Companies",
        "oversold": "Oversold (RSI < 30)",
        "overbought": "Overbought (RSI > 70)",
        "high_volume": "High Volume",
        "bullish": "Bullish Signals",
        "bearish": "Bearish Signals",
        "near_52w_low": "Near 52-Week Low",
        "near_52w_high": "Near 52-Week High",
    }
    criteria = st.selectbox("Filter", options=list(filter_labels.keys()), format_func=lambda x: filter_labels[x])

    if st.button("Scan Market", type="primary"):
        with st.spinner("Scanning all companies..."):
            scan = scan_market(criteria)

        matches = scan.get("matches", [])
        st.subheader(f"Results: {len(matches)} match(es) — Filter: {criteria}")
        if matches:
            st.dataframe(pd.DataFrame(matches), width='stretch', hide_index=True)
        else:
            st.info("No companies match this filter.")

        with st.expander("Raw JSON"):
            st.json(scan)


# ════════════════════════════════════════════════════════════════════════
# PAGE: Sector Heatmap
# ════════════════════════════════════════════════════════════════════════
elif page == "🌡️ Sector Heatmap":
    st.title("🌡️ Sector Performance Heatmap")

    if st.button("Load Heatmap", type="primary"):
        with st.spinner("Fetching sector data..."):
            heatmap = get_sector_heatmap()

        sectors = heatmap.get("sectors", [])
        if sectors:
            df = pd.DataFrame(sectors)
            pct_cols = [c for c in df.columns if "change" in c.lower() or "pct" in c.lower()]
            st.dataframe(
                df.style.map(
                    lambda v: f"color: {'green' if isinstance(v, (int, float)) and v > 0 else 'red'}" if isinstance(v, (int, float)) else "",
                    subset=pct_cols,
                ) if pct_cols else df,
                width='stretch',
                hide_index=True,
            )

            # Bar chart of 1-day changes
            pct_col = None
            for c in df.columns:
                if "1d" in c.lower() or "1_day" in c.lower() or "day_change" in c.lower():
                    pct_col = c
                    break
            if pct_col is None:
                for c in df.columns:
                    if "change" in c.lower() or "pct" in c.lower():
                        pct_col = c
                        break
            name_col = "sector" if "sector" in df.columns else df.columns[0]
            if pct_col:
                chart_df = df[[name_col, pct_col]].set_index(name_col)
                st.subheader("1-Day Change (%)")
                st.bar_chart(chart_df)
        else:
            st.warning("No sector data returned.")

        with st.expander("Raw JSON"):
            st.json(heatmap)


# ════════════════════════════════════════════════════════════════════════
# PAGE: Portfolio
# ════════════════════════════════════════════════════════════════════════
elif page == "💰 Portfolio":
    st.title("💰 Portfolio Simulator")

    # --- User management ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("👤 User Management")
    users = list_users()
    user_names = {u["id"]: u["username"] for u in users}

    with st.sidebar.expander("Create New User"):
        new_name = st.text_input("Username", key="new_user")
        if st.button("Create User"):
            if new_name.strip():
                try:
                    u = create_user(new_name.strip())
                    st.success(f"Created '{u['username']}' (ID {u['id']})")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
            else:
                st.warning("Enter a username.")

    if not users:
        st.info("No users yet. Create one in the sidebar.")
        st.stop()

    selected_user_id = st.sidebar.selectbox(
        "Select User",
        options=[u["id"] for u in users],
        format_func=lambda uid: f"{user_names[uid]} (ID {uid})",
    )
    user = get_user(selected_user_id)
    st.markdown(f"**Logged in as:** {user['username']}  (ID: {user['id']})")

    # --- Tabs ---
    tab_buy, tab_sell, tab_portfolio, tab_history = st.tabs(
        ["📈 Buy", "📉 Sell", "💼 Portfolio & P&L", "📜 History"]
    )

    # ── BUY TAB ──────────────────────────────────────────────────────
    with tab_buy:
        st.subheader("Buy Stocks")
        buy_company = st.selectbox("Company", COMPANY_OPTIONS, key="buy_co")
        bname, bsym = _parse_company(buy_company)
        buy_qty = st.number_input("Quantity", min_value=1, value=1, step=1, key="buy_qty")
        buy_date = st.date_input("Buy Date", value=date.today(), key="buy_date")

        if st.button("Buy", type="primary", key="buy_btn"):
            date_str = buy_date.strftime("%Y-%m-%d")
            with st.spinner(f"Fetching {bsym} price on {date_str}..."):
                try:
                    txn = buy_stock(user["id"], bsym, bname, buy_qty, date_str)
                    cur = _currency(bsym)
                    st.success(
                        f"✅ Bought **{txn['quantity']}** shares of **{bsym}** "
                        f"@ {cur}{txn['price_per_share']:.2f} each  \n"
                        f"**Total:** {cur}{txn['total_amount']:.2f}  |  Date: {txn['transaction_date']}"
                    )
                except ValueError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"Error: {e}")

    # ── SELL TAB ─────────────────────────────────────────────────────
    with tab_sell:
        st.subheader("Sell Stocks")
        holdings = get_holdings(user["id"])
        if not holdings:
            st.info("No holdings to sell. Buy stocks first!")
        else:
            holding_options = [f"{h['company_name']} ({h['symbol']}) — {h['total_shares']} shares" for h in holdings]
            sell_choice = st.selectbox("Select Holding", holding_options, key="sell_hold")
            idx = holding_options.index(sell_choice)
            h = holdings[idx]

            sell_qty = st.number_input("Quantity to sell", min_value=1, max_value=h["total_shares"], value=1, step=1, key="sell_qty")
            sell_date = st.date_input("Sell Date", value=date.today(), key="sell_date")

            if st.button("Sell", type="primary", key="sell_btn"):
                date_str = sell_date.strftime("%Y-%m-%d")
                with st.spinner(f"Fetching {h['symbol']} price on {date_str}..."):
                    try:
                        txn = sell_stock(user["id"], h["symbol"], h["company_name"], sell_qty, date_str)
                        cur = _currency(h["symbol"])
                        st.success(
                            f"✅ Sold **{txn['quantity']}** shares of **{h['symbol']}** "
                            f"@ {cur}{txn['price_per_share']:.2f} each  \n"
                            f"**Revenue:** {cur}{txn['total_amount']:.2f}  |  Date: {txn['transaction_date']}"
                        )
                    except ValueError as e:
                        st.error(str(e))
                    except Exception as e:
                        st.error(f"Error: {e}")

    # ── PORTFOLIO & P&L TAB ──────────────────────────────────────────
    with tab_portfolio:
        st.subheader("Portfolio & Live P&L")
        holdings = get_holdings(user["id"])
        if not holdings:
            st.info("No holdings yet.")
        else:
            if st.button("Refresh Live P&L", type="primary", key="pnl_btn"):
                with st.spinner("Fetching live prices..."):
                    enriched = portfolio_summary(user["id"], holdings)

                df = pd.DataFrame(enriched)
                display_cols = ["symbol", "company_name", "total_shares", "avg_buy_price",
                                "total_invested", "current_price", "current_value",
                                "profit_loss", "profit_loss_pct"]
                df_display = df[[c for c in display_cols if c in df.columns]]

                # Style P&L columns
                def color_pnl(val):
                    if isinstance(val, (int, float)):
                        return f"color: {'green' if val >= 0 else 'red'}; font-weight: bold"
                    return ""

                pnl_cols = [c for c in ["profit_loss", "profit_loss_pct"] if c in df_display.columns]
                styled = df_display.style.map(color_pnl, subset=pnl_cols) if pnl_cols else df_display
                st.dataframe(styled, width='stretch', hide_index=True)

                # Totals
                total_inv = sum(h.get("total_invested", 0) for h in enriched)
                total_val = sum(h.get("current_value", 0) or 0 for h in enriched)
                total_pnl = total_val - total_inv
                pnl_pct = (total_pnl / total_inv * 100) if total_inv else 0

                st.markdown("---")
                tc1, tc2, tc3, tc4 = st.columns(4)
                tc1.metric("Total Invested", f"{total_inv:,.2f}")
                tc2.metric("Current Value", f"{total_val:,.2f}")
                tc3.metric("Net P&L", f"{total_pnl:,.2f}", delta=f"{pnl_pct:+.2f}%")
                tc4.metric("Return %", f"{pnl_pct:+.2f}%")
            else:
                # Show offline holdings
                st.dataframe(pd.DataFrame(holdings), width='stretch', hide_index=True)

    # ── HISTORY TAB ──────────────────────────────────────────────────
    with tab_history:
        st.subheader("Transaction History")
        txns = get_transactions(user["id"])
        if txns:
            df = pd.DataFrame(txns)
            cols_order = ["id", "transaction_date", "action", "symbol", "company_name",
                          "quantity", "price_per_share", "total_amount"]
            df = df[[c for c in cols_order if c in df.columns]]
            st.dataframe(df, width='stretch', hide_index=True)
        else:
            st.info("No transactions yet.")


# ════════════════════════════════════════════════════════════════════════
# PAGE: AI Chatbot
# ════════════════════════════════════════════════════════════════════════
elif page == "🤖 AI Chatbot":
    st.title("🤖 AI Stock Chatbot")
    st.caption("Ask natural-language questions about stocks, portfolio, P&L — powered by RapidAPI Claude + live tools")

    import http.client
    import re

    RAPIDAPI_KEY  = "6b83508bd3msh714829b57afdbe3p1a7b49jsn7f6ddf4fc276"
    RAPIDAPI_HOST = "open-ai21.p.rapidapi.com"

    # ── Direct tool mapping ──────────────────────────────────────────
    TOOL_MAP = {
        "list_companies": lambda **kw: json.dumps({v[1]: v[0] for _, v in COMPANIES.items()}),
        "get_stock_data": lambda symbol, **kw: json.dumps(fetch_stock_data(symbol), default=str),
        "get_historical_data": lambda symbol, period="1mo", **kw: json.dumps(fetch_historical_data(symbol, period), default=str),
        "get_options_chain": lambda symbol, **kw: json.dumps(fetch_options_data(symbol), default=str),
        "calculate_greeks": lambda symbol, **kw: _calc_greeks_fn(symbol),
        "get_news": lambda company_name, symbol, **kw: json.dumps(fetch_news(company_name, symbol), default=str),
        "generate_trading_signal": lambda symbol, **kw: json.dumps(generate_signal(symbol, timeframe="3mo"), default=str),
        "detect_unusual_activity": lambda symbol, **kw: json.dumps(detect_unusual_activity(symbol), default=str),
        "scan_market": lambda filter_criteria="all", **kw: json.dumps(scan_market(filter_criteria), default=str),
        "get_sector_heatmap": lambda **kw: json.dumps(get_sector_heatmap(), default=str),
        "list_portfolio_users": lambda **kw: json.dumps(list_users(), default=str),
        "get_portfolio_summary": lambda user_id, **kw: _get_portfolio_summary_fn(int(float(user_id))),
        "get_transaction_history": lambda user_id, symbol="", **kw: json.dumps(get_transactions(int(float(user_id)), symbol or None), default=str),
    }

    def _calc_greeks_fn(symbol):
        stock = fetch_stock_data(symbol)
        opts = fetch_options_data(symbol)
        spot = stock.get("price", 0)
        if spot and opts.get("available"):
            return json.dumps(build_contracts_from_chain(spot, opts), default=str)
        return json.dumps({"error": "Options data not available"})

    def _get_portfolio_summary_fn(user_id):
        holdings = get_holdings(user_id)
        if not holdings:
            return json.dumps({"message": "No holdings"})
        enriched = portfolio_summary(user_id, holdings)
        total_inv = sum(h["total_invested"] for h in enriched)
        total_val = sum(h["current_value"] or 0 for h in enriched)
        pnl = round(total_val - total_inv, 2)
        pct = round((pnl / total_inv) * 100, 2) if total_inv else 0
        return json.dumps({
            "holdings": enriched,
            "totals": {"total_invested": round(total_inv, 2), "current_value": round(total_val, 2),
                       "net_profit_loss": pnl, "profit_loss_pct": pct},
        }, default=str)

    # ── RapidAPI call ────────────────────────────────────────────────
    def _call_rapidapi_st(messages):
        conn = http.client.HTTPSConnection(RAPIDAPI_HOST, timeout=60)
        payload = json.dumps({"messages": messages, "web_access": False})
        headers = {
            "x-rapidapi-key": RAPIDAPI_KEY,
            "x-rapidapi-host": RAPIDAPI_HOST,
            "Content-Type": "application/json",
        }
        conn.request("POST", "/claude3", payload, headers)
        res = conn.getresponse()
        data = res.read().decode("utf-8")
        conn.close()
        try:
            parsed = json.loads(data)
            if isinstance(parsed, dict):
                return (parsed.get("result") or parsed.get("response")
                        or parsed.get("content") or parsed.get("message")
                        or parsed.get("text") or parsed.get("answer")
                        or json.dumps(parsed))
            return str(parsed)
        except json.JSONDecodeError:
            return data

    def _parse_tool_call_st(text):
        match = re.search(r'TOOL_CALL:\s*(\{[^}]*\})', text, re.DOTALL)
        if match:
            try:
                call = json.loads(match.group(1))
                if "name" in call:
                    return call, text[:match.start()].strip()
            except json.JSONDecodeError:
                pass
        return None, text

    TOOL_PROMPT = """\
You have access to these tools. To call a tool, reply with EXACTLY:
TOOL_CALL: {"name": "<tool_name>", "args": {<arguments>}}

Tools:
1. list_companies() → List tracked companies.
2. get_stock_data(symbol) → Live price, volume, market cap, etc. Use .NS for Indian stocks.
3. get_historical_data(symbol, period="1mo") → OHLCV history.
4. get_options_chain(symbol) → Options chain.
5. calculate_greeks(symbol) → Black-Scholes Greeks.
6. get_news(company_name, symbol) → Latest news.
7. generate_trading_signal(symbol) → BUY/SELL/HOLD signal.
8. detect_unusual_activity(symbol) → Unusual volume/price activity.
9. scan_market(filter_criteria="all") → Scan all companies with filter.
10. get_sector_heatmap() → Sector performance.
11. list_portfolio_users() → List portfolio users.
12. get_portfolio_summary(user_id) → Portfolio P&L summary.
13. get_transaction_history(user_id, symbol="") → Transaction history.

Rules: ONE TOOL_CALL per response. Use ₹ for .NS stocks, $ for US. Never guess data.
For portfolio: first list_portfolio_users, then get_portfolio_summary."""

    SYS_MSG = f"You are an expert stock analyst assistant.\nCompanies: AAPL, GOOGL, MSFT, AMZN, TSLA (US), RELIANCE.NS, TCS.NS, INFY.NS, HDFCBANK.NS, WIPRO.NS (India).\n{TOOL_PROMPT}"

    # ── Session state ────────────────────────────────────────────────
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    if "api_messages" not in st.session_state:
        # Prime with system context
        st.session_state.api_messages = [
            {"role": "user", "content": SYS_MSG + "\nAcknowledge briefly."},
            {"role": "assistant", "content": "I'm ready to help with stock analysis. I have access to 13 tools for live data, signals, options, portfolio tracking and more. What would you like to know?"},
        ]

    # Display chat history
    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    if prompt := st.chat_input("Ask about stocks, portfolio, P&L..."):
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            st.session_state.api_messages.append({"role": "user", "content": prompt})
            answer = ""

            try:
                max_rounds = 8
                for round_num in range(max_rounds):
                    with st.spinner("Thinking..." if round_num == 0 else "Analyzing data..."):
                        reply = _call_rapidapi_st(st.session_state.api_messages)

                    tool_call, remaining = _parse_tool_call_st(reply)

                    if tool_call is None:
                        answer = reply
                        st.session_state.api_messages.append({"role": "assistant", "content": reply})
                        break

                    # Execute tool
                    tool_name = tool_call["name"]
                    tool_args = tool_call.get("args", {})
                    if remaining:
                        st.caption(f"💭 {remaining}")
                    st.caption(f"🔧 Calling `{tool_name}({json.dumps(tool_args, default=str)})`")

                    tool_fn = TOOL_MAP.get(tool_name)
                    if tool_fn:
                        try:
                            with st.spinner(f"Running {tool_name}..."):
                                result_text = tool_fn(**tool_args)
                            st.caption(f"✓ Got {len(result_text)} chars")
                        except Exception as te:
                            result_text = json.dumps({"error": str(te)})
                            st.caption(f"⚠️ Tool error: {te}")
                    else:
                        result_text = json.dumps({"error": f"Unknown tool: {tool_name}"})

                    if len(result_text) > 8000:
                        result_text = result_text[:8000] + "\n...(truncated)"

                    st.session_state.api_messages.append({"role": "assistant", "content": reply})
                    st.session_state.api_messages.append({
                        "role": "user",
                        "content": f"TOOL_RESULT for {tool_name}:\n{result_text}\n\nAnalyze this data. Give a clear answer with specific numbers. Do NOT call another tool unless absolutely necessary."
                    })
                else:
                    answer = "Max tool rounds reached."

                st.markdown(answer)
                st.session_state.chat_messages.append({"role": "assistant", "content": answer})

            except Exception as e:
                err_msg = f"❌ Error: {e}"
                st.error(err_msg)
                st.session_state.chat_messages.append({"role": "assistant", "content": err_msg})

            # Trim conversation
            if len(st.session_state.api_messages) > 30:
                st.session_state.api_messages = st.session_state.api_messages[:2] + st.session_state.api_messages[-24:]

    if st.sidebar.button("🗑️ Clear Chat"):
        st.session_state.chat_messages = []
        st.session_state.api_messages = [
            {"role": "user", "content": SYS_MSG + "\nAcknowledge briefly."},
            {"role": "assistant", "content": "I'm ready to help with stock analysis. What would you like to know?"},
        ]
        st.rerun()
