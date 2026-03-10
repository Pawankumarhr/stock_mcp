"""Quick test: verify all tool imports load cleanly."""
import sys, os, io, contextlib, warnings, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Importing all tools (with stdout/stderr suppressed)...")
t0 = time.time()

buf = io.StringIO()
err = io.StringIO()
with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err), \
     warnings.catch_warnings():
    warnings.simplefilter("ignore")
    from tools.live_stock import (
        COMPANIES, fetch_stock_data, fetch_historical_data, fetch_options_data,
    )
    from tools.news_fetch import fetch_news
    from tools.generating_signal import generate_signal
    from tools.cal_greek import build_contracts_from_chain
    from tools.detect_unusual import detect_unusual_activity
    from tools.scan_market import scan_market
    from tools.sector_heatmap import get_sector_heatmap

captured_out = buf.getvalue()
captured_err = err.getvalue()

print(f"✅ All imports loaded in {time.time()-t0:.2f}s")
print(f"   Captured stdout: {len(captured_out)} chars")
print(f"   Captured stderr: {len(captured_err)} chars")
if captured_out:
    print(f"   stdout preview: {captured_out[:200]}")
if captured_err:
    print(f"   stderr preview: {captured_err[:200]}")

print(f"\n   Companies: {list(COMPANIES.keys())}")

# Quick fetch test
print("\nFetching WIPRO.NS live data...")
t1 = time.time()
data = fetch_stock_data("WIPRO.NS")
print(f"✅ Got data in {time.time()-t1:.2f}s  —  price: {data.get('price')}")
