"""
Shared caching, retry, and rate-limiting utilities for yfinance tools.
Prevents Yahoo Finance 429 (Too Many Requests) errors on cloud hosts like Render.
"""

import time
import threading
import functools
import hashlib
import json

# ── TTL Cache ────────────────────────────────────────────────────────────
_cache: dict[str, tuple[float, object]] = {}
_cache_lock = threading.Lock()


def ttl_cache(ttl_seconds: int = 300):
    """Decorator: cache function results for `ttl_seconds` (default 5 min)."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Build a unique key from function name + args
            key_data = f"{func.__module__}.{func.__name__}:{args}:{sorted(kwargs.items())}"
            key = hashlib.md5(key_data.encode()).hexdigest()

            with _cache_lock:
                if key in _cache:
                    expires, value = _cache[key]
                    if time.time() < expires:
                        return value

            # Call the actual function
            result = func(*args, **kwargs)

            with _cache_lock:
                _cache[key] = (time.time() + ttl_seconds, result)

            return result
        return wrapper
    return decorator


def clear_cache():
    """Clear all cached data."""
    with _cache_lock:
        _cache.clear()


# ── Rate Limiter ─────────────────────────────────────────────────────────
_last_call_time = 0.0
_rate_lock = threading.Lock()
MIN_INTERVAL = 0.5  # seconds between yfinance calls


def rate_limit():
    """Sleep if needed to space out Yahoo Finance requests."""
    global _last_call_time
    with _rate_lock:
        now = time.time()
        elapsed = now - _last_call_time
        if elapsed < MIN_INTERVAL:
            time.sleep(MIN_INTERVAL - elapsed)
        _last_call_time = time.time()


# ── Retry with Backoff ───────────────────────────────────────────────────
def retry_on_rate_limit(max_retries: int = 3, base_delay: float = 2.0):
    """Decorator: retry function on any exception with exponential backoff."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_err = None
            for attempt in range(max_retries):
                try:
                    rate_limit()
                    return func(*args, **kwargs)
                except Exception as e:
                    last_err = e
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        time.sleep(delay)
            raise last_err
        return wrapper
    return decorator
