"""
Options Greeks Calculator — Pure Black-Scholes from scratch.
No external math/stats libraries. All formulas implemented manually.

Black-Scholes assumes:
  - European-style options
  - No dividends (simplified)
  - Constant volatility & risk-free rate
  - Log-normal distribution of returns

References:
  d1 = [ln(S/K) + (r + σ²/2) * T] / (σ * √T)
  d2 = d1 - σ * √T

Greeks:
  Delta (call) = N(d1)           Delta (put) = N(d1) - 1
  Gamma        = N'(d1) / (S * σ * √T)
  Theta (call) = -(S * N'(d1) * σ) / (2√T) - r * K * e^(-rT) * N(d2)
  Theta (put)  = -(S * N'(d1) * σ) / (2√T) + r * K * e^(-rT) * N(-d2)
  Vega         = S * N'(d1) * √T
"""

import math
from datetime import datetime

# ──────────────────────────────────────────────────────
#  Pure math implementations (NO scipy, NO numpy)
# ──────────────────────────────────────────────────────

_SQRT_2PI = math.sqrt(2 * math.pi)   # ≈ 2.506628


def _pdf_standard_normal(x: float) -> float:
    """Standard normal probability density function N'(x)."""
    return math.exp(-0.5 * x * x) / _SQRT_2PI


def _cdf_standard_normal(x: float) -> float:
    """
    Standard normal cumulative distribution function N(x).
    Uses the Abramowitz & Stegun rational approximation (error < 7.5e-8).
    """
    if x < -8.0:
        return 0.0
    if x > 8.0:
        return 1.0

    # Constants for the approximation
    b1 = 0.319381530
    b2 = -0.356563782
    b3 = 1.781477937
    b4 = -1.821255978
    b5 = 1.330274429
    p = 0.2316419

    t = 1.0 / (1.0 + p * abs(x))
    t2 = t * t
    t3 = t2 * t
    t4 = t3 * t
    t5 = t4 * t

    pdf = _pdf_standard_normal(x)
    cdf = 1.0 - pdf * (b1 * t + b2 * t2 + b3 * t3 + b4 * t4 + b5 * t5)

    if x < 0:
        cdf = 1.0 - cdf

    return cdf


# ──────────────────────────────────────────────────────
#  Black-Scholes core
# ──────────────────────────────────────────────────────

def _d1(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Calculate d1 in Black-Scholes formula."""
    return (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))


def _d2(d1_val: float, sigma: float, T: float) -> float:
    """Calculate d2 = d1 - σ√T."""
    return d1_val - sigma * math.sqrt(T)


# ──────────────────────────────────────────────────────
#  Greeks calculations — PURE MATH
# ──────────────────────────────────────────────────────

def calc_delta(S, K, T, r, sigma, option_type="call"):
    """
    Delta: rate of change of option price w.r.t. underlying price.
    Call delta ∈ [0, 1], Put delta ∈ [-1, 0]
    """
    d1 = _d1(S, K, T, r, sigma)
    if option_type == "call":
        return round(_cdf_standard_normal(d1), 6)
    else:
        return round(_cdf_standard_normal(d1) - 1.0, 6)


def calc_gamma(S, K, T, r, sigma):
    """
    Gamma: rate of change of delta w.r.t. underlying price.
    Same for both calls and puts.
    """
    d1 = _d1(S, K, T, r, sigma)
    return round(_pdf_standard_normal(d1) / (S * sigma * math.sqrt(T)), 6)


def calc_theta(S, K, T, r, sigma, option_type="call"):
    """
    Theta: rate of change of option price w.r.t. time (per day).
    Expressed as daily theta (÷ 365).
    """
    d1 = _d1(S, K, T, r, sigma)
    d2 = _d2(d1, sigma, T)
    sqrt_T = math.sqrt(T)

    common = -(S * _pdf_standard_normal(d1) * sigma) / (2.0 * sqrt_T)

    if option_type == "call":
        theta = common - r * K * math.exp(-r * T) * _cdf_standard_normal(d2)
    else:
        theta = common + r * K * math.exp(-r * T) * _cdf_standard_normal(-d2)

    return round(theta / 365.0, 6)  # per-day theta


def calc_vega(S, K, T, r, sigma):
    """
    Vega: rate of change of option price w.r.t. volatility.
    Per 1% move in vol (÷ 100). Same for calls and puts.
    """
    d1 = _d1(S, K, T, r, sigma)
    vega = S * _pdf_standard_normal(d1) * math.sqrt(T)
    return round(vega / 100.0, 6)  # per 1% vol change


def calc_option_price(S, K, T, r, sigma, option_type="call"):
    """Black-Scholes option price — pure math."""
    d1 = _d1(S, K, T, r, sigma)
    d2 = _d2(d1, sigma, T)
    if option_type == "call":
        price = S * _cdf_standard_normal(d1) - K * math.exp(-r * T) * _cdf_standard_normal(d2)
    else:
        price = K * math.exp(-r * T) * _cdf_standard_normal(-d2) - S * _cdf_standard_normal(-d1)
    return round(price, 4)


# ──────────────────────────────────────────────────────
#  Full Greeks bundle
# ──────────────────────────────────────────────────────

def calculate_greeks(option_contract: dict) -> dict:
    """
    Calculate all Greeks for an option contract.

    option_contract keys:
        S      : underlying price (spot)
        K      : strike price
        T      : time to expiry in years (e.g. 30 days = 30/365)
        r      : risk-free rate (annual, e.g. 0.05 for 5%)
        sigma  : implied volatility (annual, e.g. 0.25 for 25%)
        type   : 'call' or 'put'
    """
    S = option_contract["S"]
    K = option_contract["K"]
    T = option_contract["T"]
    r = option_contract["r"]
    sigma = option_contract["sigma"]
    opt_type = option_contract.get("type", "call")

    if T <= 0:
        # Expired — intrinsic value only
        intrinsic = max(S - K, 0) if opt_type == "call" else max(K - S, 0)
        return {
            "option_type": opt_type,
            "S": S, "K": K, "T": T, "r": r, "sigma": sigma,
            "bs_price": round(intrinsic, 4),
            "delta": 1.0 if (opt_type == "call" and S > K) else (-1.0 if (opt_type == "put" and K > S) else 0.0),
            "gamma": 0.0, "theta": 0.0, "vega": 0.0,
            "status": "EXPIRED",
        }

    return {
        "option_type": opt_type,
        "S": S,
        "K": K,
        "T_years": round(T, 6),
        "T_days": round(T * 365, 1),
        "r": r,
        "sigma": sigma,
        "bs_price": calc_option_price(S, K, T, r, sigma, opt_type),
        "delta": calc_delta(S, K, T, r, sigma, opt_type),
        "gamma": calc_gamma(S, K, T, r, sigma),
        "theta": calc_theta(S, K, T, r, sigma, opt_type),
        "vega": calc_vega(S, K, T, r, sigma),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ──────────────────────────────────────────────────────
#  Build contracts from live options chain data
# ──────────────────────────────────────────────────────

def build_contracts_from_chain(spot_price: float, chain: dict, r: float = 0.05) -> list:
    """
    Build option contracts from a fetched options chain and compute Greeks.
    Returns list of Greeks results for top calls and puts.
    """
    if not chain.get("available"):
        return []

    from datetime import datetime as dt

    # Estimate T from expiration date
    try:
        exp_date = dt.strptime(chain["expiration"], "%Y-%m-%d")
        days_to_exp = max((exp_date - dt.now()).days, 1)
    except Exception:
        days_to_exp = 30  # fallback

    T = days_to_exp / 365.0
    results = []

    for opt_type, key in [("call", "top_calls"), ("put", "top_puts")]:
        for item in chain.get(key, []):
            iv = item.get("impliedVolatility", 0.25)
            if iv <= 0:
                iv = 0.25  # fallback
            contract = {
                "S": spot_price,
                "K": item["strike"],
                "T": T,
                "r": r,
                "sigma": iv,
                "type": opt_type,
            }
            greeks = calculate_greeks(contract)
            greeks["market_price"] = item.get("lastPrice", "N/A")
            results.append(greeks)

    return results


# ──────────────────────────────────────────────────────
#  Display
# ──────────────────────────────────────────────────────

def display_greeks(greeks_list: list):
    """Pretty-print Greeks for all contracts."""
    if not greeks_list:
        print("\n  ⚠️  No options contracts available to calculate Greeks.")
        return

    print(f"\n{'━' * 70}")
    print(f"  🧮 OPTIONS GREEKS (Black-Scholes — Pure Math, No Libraries)")
    print(f"{'━' * 70}")
    print(f"  {'Type':<5} {'Strike':>8} {'BS Price':>9} {'MktPrice':>9} {'Delta':>8} {'Gamma':>8} {'Theta':>8} {'Vega':>8}")
    print(f"  {'─' * 65}")

    for g in greeks_list:
        otype = g["option_type"].upper()[:4]
        strike = f"{g['K']:>8.2f}"
        bs = f"{g['bs_price']:>9.4f}"
        mkt = f"{g.get('market_price', 'N/A'):>9}" if not isinstance(g.get('market_price'), (int, float)) else f"{g['market_price']:>9.2f}"
        delta = f"{g['delta']:>8.4f}"
        gamma = f"{g['gamma']:>8.6f}"
        theta = f"{g['theta']:>8.6f}"
        vega = f"{g['vega']:>8.6f}"
        print(f"  {otype:<5} {strike} {bs} {mkt} {delta} {gamma} {theta} {vega}")

    print(f"  {'─' * 65}")
    t_info = greeks_list[0]
    print(f"  Spot: {t_info['S']}  |  Days to Exp: {t_info.get('T_days', 'N/A')}")
    print(f"  Risk-free rate: {t_info['r']*100:.1f}%  |  Method: Black-Scholes (pure math)")
    print(f"{'━' * 70}")
