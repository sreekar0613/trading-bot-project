"""
Fetch daily OHLCV bars from Alpaca and store in trading_bot.db (price_history table).

Usage:
    python data/fetch_historical_data.py              # defaults to AAPL
    python data/fetch_historical_data.py MSFT
    python data/fetch_historical_data.py AAPL MSFT NVDA
"""

import os
import sys
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

# ── Config ──────────────────────────────────────────────────────────────────
START_DATE = datetime(2020, 1, 1, tzinfo=timezone.utc)
END_DATE   = datetime(2024, 12, 31, tzinfo=timezone.utc)

# Resolve paths relative to repo root (one level up from this file)
REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH   = REPO_ROOT / "trading_bot.db"
ENV_PATH  = REPO_ROOT / ".env"


def get_data_client() -> StockHistoricalDataClient:
    load_dotenv(ENV_PATH)
    api_key    = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")
    if not api_key or not secret_key:
        print("ERROR: ALPACA_API_KEY or ALPACA_SECRET_KEY missing from .env")
        sys.exit(1)
    return StockHistoricalDataClient(api_key=api_key, secret_key=secret_key)


def fetch_bars(client: StockHistoricalDataClient, symbol: str) -> list[dict]:
    """Return a list of bar dicts for the given symbol."""
    request = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame.Day,
        start=START_DATE,
        end=END_DATE,
        feed="iex",          # free feed; switch to "sip" on paid plan
        adjustment="all",    # dividend + split adjusted
    )
    bars_response = client.get_stock_bars(request)
    bars = bars_response[symbol]   # list of Bar objects
    return [
        {
            "symbol": symbol,
            "date":   bar.timestamp.strftime("%Y-%m-%d"),
            "open":   float(bar.open),
            "high":   float(bar.high),
            "low":    float(bar.low),
            "close":  float(bar.close),
            "volume": int(bar.volume),
        }
        for bar in bars
    ]


def upsert_bars(bars: list[dict]) -> int:
    """Insert or replace bars into price_history. Returns count inserted."""
    if not bars:
        return 0
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executemany(
            """
            INSERT OR REPLACE INTO price_history
                (symbol, date, open, high, low, close, volume)
            VALUES
                (:symbol, :date, :open, :high, :low, :close, :volume)
            """,
            bars,
        )
        conn.commit()
    finally:
        conn.close()
    return len(bars)


def fetch_and_store(client: StockHistoricalDataClient, symbol: str) -> None:
    symbol = symbol.upper()
    print(f"\nFetching {symbol} …", flush=True)

    try:
        bars = fetch_bars(client, symbol)
    except Exception as exc:
        print(f"  ERROR fetching {symbol}: {exc}")
        return

    if not bars:
        print(f"  WARNING: no bars returned for {symbol}")
        return

    inserted = upsert_bars(bars)
    first_date = bars[0]["date"]
    last_date  = bars[-1]["date"]
    print(f"  Symbol   : {symbol}")
    print(f"  Date range: {first_date} → {last_date}")
    print(f"  Bars stored: {inserted:,}")


def main() -> None:
    tickers = sys.argv[1:] if len(sys.argv) > 1 else ["AAPL"]
    client  = get_data_client()
    print(f"Connected to Alpaca data API")
    print(f"Database: {DB_PATH}")
    print(f"Period  : {START_DATE.date()} → {END_DATE.date()}")

    for ticker in tickers:
        fetch_and_store(client, ticker)

    print("\nDone.")


if __name__ == "__main__":
    main()
