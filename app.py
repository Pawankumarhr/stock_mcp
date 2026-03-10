import json, os
from datetime import datetime
from tools.live_stock import (
    COMPANIES, display_menu, fetch_stock_data, fetch_historical_data,
    fetch_options_data, display_stock_data, display_historical, display_options,
)
from tools.news_fetch import fetch_news, display_news
from tools.generating_signal import generate_signal, display_signal
from tools.cal_greek import build_contracts_from_chain, display_greeks
from tools.detect_unusual import detect_unusual_activity, display_unusual_activity
from tools.scan_market import (
    FILTER_OPTIONS, scan_market, display_filter_menu, display_scan_results,
)
from tools.sector_heatmap import get_sector_heatmap, display_sector_heatmap

OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def _convert_floats(obj):
    """Recursively convert floats to full decimal strings (no scientific notation)."""
    if isinstance(obj, float):
        return float(f"{obj:.10f}")
    if isinstance(obj, dict):
        return {k: _convert_floats(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert_floats(i) for i in obj]
    return obj


def _json_dumps_full_precision(data):
    """Serialize to JSON with full decimal precision (no 6.7e-05 style)."""
    import re
    raw = json.dumps(data, indent=2, default=str)
    # Replace any remaining scientific notation floats in the JSON string
    def _expand(match):
        return f"{float(match.group()):.10f}".rstrip('0').rstrip('.')
    return re.sub(r'-?\d+\.\d+e[+-]?\d+', _expand, raw)


def save_json(data: dict, symbol: str):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(OUTPUT_DIR, f"{symbol}_{ts}.json")
    with open(path, "w", encoding="utf-8") as f:
        f.write(_json_dumps_full_precision(data))
    print(f"\n  💾 JSON saved → {path}")


def main():
    while True:
        display_menu()
        choice = input("\n  Select a company (0-10) or [S]can / [H]eatmap: ").strip().upper()
        if choice == "0":
            print("\n  Goodbye! 👋\n")
            break

        # --- Tool 9: Market Scanner (global) ---
        if choice == "S":
            display_filter_menu()
            filt = input("  Choose filter (1-8): ").strip()
            criteria = FILTER_OPTIONS.get(filt, "all")
            try:
                scan_data = scan_market(criteria)
                display_scan_results(scan_data)
                save_json(scan_data, f"scan_{criteria}")
            except Exception as e:
                print(f"  ❌ Scan error: {e}")
            continue

        # --- Tool 10: Sector Heatmap (global) ---
        if choice == "H":
            try:
                heatmap = get_sector_heatmap()
                display_sector_heatmap(heatmap)
                save_json(heatmap, "sector_heatmap")
            except Exception as e:
                print(f"  ❌ Heatmap error: {e}")
            continue

        if choice not in COMPANIES:
            print("\n  ⚠️  Invalid choice.")
            continue

        name, symbol = COMPANIES[choice]
        result = {"company": name, "symbol": symbol}

        # --- Tool 1: Live Stock Data ---
        print(f"\n  ⏳ Fetching live stock data for {name}...")
        try:
            stock = fetch_stock_data(symbol)
            display_stock_data(stock)
            result["stock_data"] = stock
        except Exception as e:
            print(f"  ❌ Stock error: {e}")

        # --- Tool 1b: Historical OHLC ---
        print(f"  ⏳ Fetching historical OHLC...")
        try:
            hist = fetch_historical_data(symbol)
            display_historical(hist)
            result["historical_ohlc"] = hist
        except Exception as e:
            print(f"  ❌ History error: {e}")

        # --- Tool 1c: Options Chain ---
        print(f"  ⏳ Fetching options chain...")
        try:
            opts = fetch_options_data(symbol)
            display_options(opts)
            result["options_chain"] = opts
        except Exception as e:
            print(f"  ❌ Options error: {e}")

        # --- Tool 4: Options Greeks (Black-Scholes from scratch) ---
        print(f"  ⏳ Calculating Options Greeks (pure Black-Scholes)...")
        try:
            spot = result.get("stock_data", {}).get("price", 0)
            if spot and opts.get("available"):
                greeks_list = build_contracts_from_chain(spot, opts)
                display_greeks(greeks_list)
                result["options_greeks"] = greeks_list
            else:
                print(f"  ⚠️  Skipped — need live price + options chain for Greeks.")
        except Exception as e:
            print(f"  ❌ Greeks error: {e}")

        # --- Tool 2: News Fetch (NewsAPI + Google) ---
        print(f"  ⏳ Fetching news & market updates...")
        try:
            news = fetch_news(name, symbol)
            display_news(news)
            result["news"] = news
        except Exception as e:
            print(f"  ❌ News error: {e}")

        # --- Tool 3: Trading Signal ---
        print(f"  ⏳ Generating trading signal...")
        try:
            sig = generate_signal(symbol, timeframe="3mo")
            display_signal(sig)
            result["trading_signal"] = sig
        except Exception as e:
            print(f"  ❌ Signal error: {e}")

        # --- Tool 8: Detect Unusual Activity ---
        print(f"  ⏳ Detecting unusual activity...")
        try:
            unusual = detect_unusual_activity(symbol)
            display_unusual_activity(unusual)
            result["unusual_activity"] = unusual
        except Exception as e:
            print(f"  ❌ Unusual-activity error: {e}")

        # --- Save JSON ---
        save_json(result, symbol.replace(".", "_"))


if __name__ == "__main__":
    main()
