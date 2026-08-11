"""Strat de date: preia cotații de la Twelve Data REST API.

Este necesară doar o cheie API Twelve Data, nu un cont la broker. Creează un
cont gratuit la https://twelvedata.com și setează TWELVE_DATA_API_KEY.
"""
import os
import time
import threading

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ.get("TWELVE_DATA_API_KEY", "")
BASE_URL = "https://api.twelvedata.com/time_series"

# Simboluri Twelve Data. ETF-urile sunt proxy-uri lichide pentru indicii/mărfurile
# care nu sunt disponibile ca CFD-uri universale într-un feed gratuit.
INSTRUMENTS = {
    "GOLD": "XAU/USD",
    "SILVER": "XAG/USD",
    "OIL": "USO",           # United States Oil Fund
    "COPPER": "CPER",       # United States Copper Index Fund
    "US30": "DIA",          # ETF care urmărește Dow Jones (US30)
    "NAS100": "QQQ",        # ETF care urmărește Nasdaq-100
    "US10Y_PROXY": "TLT",   # obligațiuni SUA 20+ ani; preț invers față de randamente
    "EURUSD": "EUR/USD",
    "GBPUSD": "GBP/USD",
    "USDJPY": "USD/JPY",
    "USDCHF": "USD/CHF",
    "AUDUSD": "AUD/USD",
    "NZDUSD": "NZD/USD",
    "USDCAD": "USD/CAD",
    "EURJPY": "EUR/JPY",
    "GBPJPY": "GBP/JPY",
    "AUDJPY": "AUD/JPY",
    "CADJPY": "CAD/JPY",
    "CHFJPY": "CHF/JPY",
    "NZDJPY": "NZD/JPY",
}

_cache = {}
_cache_lock = threading.Lock()
# Planul gratuit are un buget de credite; cache-ul previne consumul la fiecare refresh.
_CACHE_TTL_DAILY = 20 * 60
_CACHE_TTL_INTRADAY = 15 * 60


def _fetch_candles(symbol: str, interval: str, count: int) -> pd.DataFrame:
    if not API_KEY:
        raise RuntimeError(
            "TWELVE_DATA_API_KEY nu este setată. Creează o cheie API gratuită la "
            "twelvedata.com și adaug-o în Environment Variables din Render."
        )

    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": count,
        "apikey": API_KEY,
        "format": "JSON",
    }
    response = requests.get(BASE_URL, params=params, timeout=20)
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError(f"Twelve Data a răspuns invalid pentru {symbol}.") from exc

    if response.status_code != 200 or payload.get("status") == "error":
        message = payload.get("message", response.text[:200])
        raise RuntimeError(f"Twelve Data API error [{symbol}]: {message}")

    values = payload.get("values", [])
    rows = [
        {
            "time": candle["datetime"],
            "Open": float(candle["open"]),
            "High": float(candle["high"]),
            "Low": float(candle["low"]),
            "Close": float(candle["close"]),
        }
        for candle in values
    ]
    df = pd.DataFrame(rows)
    if df.empty:
        raise RuntimeError(f"Twelve Data nu a returnat lumânări pentru {symbol}.")
    df["time"] = pd.to_datetime(df["time"], utc=True)
    return df.set_index("time").sort_index()


def _cached(key, ttl, fn):
    now = time.time()
    with _cache_lock:
        entry = _cache.get(key)
        if entry and (now - entry["ts"]) < ttl:
            return entry["data"]
    data = fn()
    with _cache_lock:
        _cache[key] = {"ts": now, "data": data}
    return data


def get_daily(name: str, count: int = 180) -> pd.DataFrame:
    """Lumânări zilnice pentru ADX, ATR și momentum."""
    symbol = INSTRUMENTS[name]
    return _cached(f"d_{name}_{count}", _CACHE_TTL_DAILY, lambda: _fetch_candles(symbol, "1day", count))


def get_intraday(name: str, count: int = 500, granularity: str = "M15") -> pd.DataFrame:
    """Lumânări intraday pentru Asia range și predictorul Day Type."""
    symbol = INSTRUMENTS[name]
    intervals = {"M1": "1min", "M5": "5min", "M15": "15min", "M30": "30min", "H1": "1h"}
    interval = intervals.get(granularity, granularity)
    return _cached(
        f"i_{name}_{count}_{interval}",
        _CACHE_TTL_INTRADAY,
        lambda: _fetch_candles(symbol, interval, count),
    )


def get_all_daily(names, count: int = 180):
    return {name: get_daily(name, count) for name in names}
