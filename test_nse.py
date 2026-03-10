import requests, json

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.nseindia.com/option-chain',
}

session = requests.Session()
session.get('https://www.nseindia.com', headers=headers, timeout=10)

# Test NIFTY index options
r1 = session.get('https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY', headers=headers, timeout=10)
print("NIFTY Status:", r1.status_code)
d1 = r1.json()
recs1 = d1.get('records', {})
print("NIFTY Expiries:", recs1.get('expiryDates', [])[:3])
print("NIFTY Underlying:", recs1.get('underlyingValue'))
print("NIFTY Data count:", len(recs1.get('data', [])))
if recs1.get('data'):
    item = recs1['data'][0]
    print("First item keys:", list(item.keys()))
    ce = item.get('CE', {})
    pe = item.get('PE', {})
    print(f"Strike: {item.get('strikePrice')}, Expiry: {item.get('expiryDate')}")
    if ce:
        print(f"  CE: last={ce.get('lastPrice')}, IV={ce.get('impliedVolatility')}, OI={ce.get('openInterest')}")
    if pe:
        print(f"  PE: last={pe.get('lastPrice')}, IV={pe.get('impliedVolatility')}, OI={pe.get('openInterest')}")

print("\n--- WIPRO Equity Options ---")
r2 = session.get('https://www.nseindia.com/api/option-chain-equities?symbol=WIPRO', headers=headers, timeout=10)
print("WIPRO Status:", r2.status_code)
d2 = r2.json()
recs2 = d2.get('records', {})
print("WIPRO Expiries:", recs2.get('expiryDates', [])[:3])
print("WIPRO Underlying:", recs2.get('underlyingValue'))
print("WIPRO Data count:", len(recs2.get('data', [])))
if recs2.get('data'):
    item = recs2['data'][0]
    ce = item.get('CE', {})
    pe = item.get('PE', {})
    print(f"Strike: {item.get('strikePrice')}, Expiry: {item.get('expiryDate')}")
    if ce:
        print(f"  CE: last={ce.get('lastPrice')}, IV={ce.get('impliedVolatility')}, OI={ce.get('openInterest')}")

print("\n--- RELIANCE ---")
r3 = session.get('https://www.nseindia.com/api/option-chain-equities?symbol=RELIANCE', headers=headers, timeout=10)
print("Status:", r3.status_code)
d3 = r3.json()
recs3 = d3.get('records', {})
print("Expiries:", recs3.get('expiryDates', [])[:3])
print("Data count:", len(recs3.get('data', [])))
