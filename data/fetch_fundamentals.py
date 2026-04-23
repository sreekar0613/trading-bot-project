"""
Fetch Alpha Vantage OVERVIEW data for every ticker in liquid_universe,
apply fundamental filters, and write qualified tickers to fundamental_universe.

Filters (all must pass):
  Market Cap       > $2B
  ROE              > 15 %
  Earnings growth  > 0 %   (YoY EPS)

P/B ratio intentionally excluded: buyback-heavy growth stocks (AAPL, MSFT, etc.)
carry inflated P/B ratios that don't reflect business quality. Entry valuation
is controlled instead by RSI < 35 and Bollinger Band technical signals.

Rate limit: Alpha Vantage free tier = 25 calls/day → 12 s delay between calls.

Usage:
    python data/fetch_fundamentals.py
"""

import os
import sys
import sqlite3
import time
import requests
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH   = REPO_ROOT / "trading_bot.db"
ENV_PATH  = REPO_ROOT / ".env"

AV_BASE_URL   = "https://www.alphavantage.co/query"
CALL_DELAY_S  = 12          # seconds between calls — stays inside 25/day free limit

# ── Watchlist override ───────────────────────────────────────────────────────
# When non-empty, process these tickers instead of reading from liquid_universe.
# Clear this list to revert to the liquid_universe-driven workflow.
WATCHLIST: list[str] = [
    "AAPL", "MSFT", "GOOGL", "NVDA", "META",  # Tech
    "JPM", "JNJ", "XOM", "PG", "V",           # Non-tech
]

# ── Filter thresholds ────────────────────────────────────────────────────────
MIN_MARKET_CAP_B    = 2.0   # $2 billion
MIN_ROE_PCT         = 15.0  # 15 %
MIN_EARNINGS_GROWTH = 0.0   # any positive YoY EPS growth


def load_api_key() -> str:
    load_dotenv(ENV_PATH)
    key = os.getenv("ALPHA_VANTAGE_API_KEY")
    if not key:
        print("ERROR: ALPHA_VANTAGE_API_KEY missing from .env")
        sys.exit(1)
    return key


def get_liquid_tickers(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("SELECT symbol FROM liquid_universe ORDER BY symbol").fetchall()
    return [r[0] for r in rows]


def fetch_overview(symbol: str, api_key: str) -> dict | None:
    """Call Alpha Vantage OVERVIEW. Returns raw JSON dict or None on error."""
    params = {"function": "OVERVIEW", "symbol": symbol, "apikey": api_key}
    try:
        resp = requests.get(AV_BASE_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        print(f"  [HTTP error] {exc}")
        return None

    # Rate-limit or empty response guard
    if "Note" in data:
        print(f"  [Rate limit hit] Alpha Vantage returned: {data['Note'][:80]}")
        return None
    if "Information" in data:
        print(f"  [API message] {data['Information'][:80]}")
        return None
    if not data.get("Symbol"):
        print(f"  [Empty response] No data returned for {symbol}")
        return None

    return data


def parse_float(value: str | None, field: str) -> float | None:
    """Convert AV string value to float; return None if missing or non-numeric."""
    if not value or value in ("None", "-", "N/A", ""):
        return None
    try:
        return float(value)
    except ValueError:
        print(f"  [Parse error] Could not convert {field}={value!r} to float")
        return None


def evaluate_ticker(symbol: str, data: dict) -> tuple[bool, dict, list[str]]:
    """
    Returns (passed, metrics_dict, failure_reasons).
    metrics_dict contains all values regardless of pass/fail.
    """
    failures: list[str] = []

    market_cap_raw = parse_float(data.get("MarketCapitalization"), "MarketCap")
    roe_raw        = parse_float(data.get("ReturnOnEquityTTM"), "ROE")
    eps_growth_raw = parse_float(data.get("QuarterlyEarningsGrowthYOY"), "EPS Growth")
    sector         = data.get("Sector", "Unknown")

    # AV returns ROE and EPS growth as decimals (0.15 = 15%)
    roe_pct        = roe_raw        * 100 if roe_raw        is not None else None
    eps_growth_pct = eps_growth_raw * 100 if eps_growth_raw is not None else None
    market_cap_b   = market_cap_raw / 1e9 if market_cap_raw is not None else None

    # ── Apply filters ────────────────────────────────────────────────────────
    if market_cap_b is None:
        failures.append("Market cap: missing data")
    elif market_cap_b <= MIN_MARKET_CAP_B:
        failures.append(f"Market cap ${market_cap_b:.2f}B ≤ ${MIN_MARKET_CAP_B}B")

    if roe_pct is None:
        failures.append("ROE: missing data")
    elif roe_pct <= MIN_ROE_PCT:
        failures.append(f"ROE {roe_pct:.1f}% ≤ {MIN_ROE_PCT}%")

    if eps_growth_pct is None:
        failures.append("Earnings growth: missing data")
    elif eps_growth_pct <= MIN_EARNINGS_GROWTH:
        failures.append(f"EPS growth {eps_growth_pct:.1f}% ≤ {MIN_EARNINGS_GROWTH}%")

    metrics = {
        "symbol":          symbol,
        "market_cap":      market_cap_raw,
        "roe":             roe_pct,
        "earnings_growth": eps_growth_pct,
        "sector":          sector,
    }
    return (len(failures) == 0, metrics, failures)


def upsert_fundamental_universe(conn: sqlite3.Connection, metrics: dict) -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    conn.execute(
        """
        INSERT OR REPLACE INTO fundamental_universe
            (symbol, market_cap, roe, sector, earnings_growth, last_updated)
        VALUES
            (:symbol, :market_cap, :roe, :sector, :earnings_growth, :last_updated)
        """,
        {**metrics, "last_updated": today},
    )
    conn.commit()


def main() -> None:
    api_key = load_api_key()
    conn    = sqlite3.connect(DB_PATH)

    tickers = WATCHLIST if WATCHLIST else get_liquid_tickers(conn)
    if not tickers:
        print("liquid_universe is empty. Run screen_by_volume.py first.")
        conn.close()
        sys.exit(0)

    print(f"Fundamental Screener — Alpha Vantage OVERVIEW")
    print(f"Database : {DB_PATH}")
    print(f"Tickers  : {', '.join(tickers)}")
    print(f"Filters  : MarketCap > ${MIN_MARKET_CAP_B}B | ROE > {MIN_ROE_PCT}% "
          f"| EPS growth > {MIN_EARNINGS_GROWTH}%")
    print(f"Rate limit: {CALL_DELAY_S}s delay between calls\n")

    passed_list:  list[dict] = []
    failed_list:  list[tuple[str, list[str]]] = []
    error_list:   list[str]  = []

    for i, symbol in enumerate(tickers):
        print(f"[{i+1}/{len(tickers)}] {symbol} …", flush=True)

        data = fetch_overview(symbol, api_key)
        if data is None:
            error_list.append(symbol)
            print(f"  → skipped (API error)\n")
        else:
            passed, metrics, failures = evaluate_ticker(symbol, data)

            cap_str = f"${metrics['market_cap']/1e9:.2f}B" if metrics["market_cap"] else "N/A"
            roe_str = f"{metrics['roe']:.1f}%"             if metrics["roe"] is not None else "N/A"
            eg_str  = f"{metrics['earnings_growth']:.1f}%" if metrics["earnings_growth"] is not None else "N/A"

            print(f"  MarketCap={cap_str}  ROE={roe_str}  EPS growth={eg_str}  Sector={metrics['sector']}")

            if passed:
                upsert_fundamental_universe(conn, metrics)
                passed_list.append(metrics)
                print(f"  → PASSED ✓\n")
            else:
                failed_list.append((symbol, failures))
                print(f"  → FAILED: {'; '.join(failures)}\n")

        # Rate-limit guard — skip delay after the last ticker
        if i < len(tickers) - 1:
            print(f"  (waiting {CALL_DELAY_S}s …)", flush=True)
            time.sleep(CALL_DELAY_S)

    conn.close()

    # ── Summary ──────────────────────────────────────────────────────────────
    print("=" * 60)
    print(f"SUMMARY")
    print(f"  Analyzed : {len(tickers)}")
    print(f"  Passed   : {len(passed_list)}")
    print(f"  Failed   : {len(failed_list)}")
    print(f"  Errors   : {len(error_list)}")

    if passed_list:
        print(f"\nQualified tickers (written to fundamental_universe):")
        print(f"  {'Symbol':<8} {'MarketCap':>10} {'ROE':>8} {'EPS Growth':>11} {'Sector'}")
        print(f"  {'-'*60}")
        for m in passed_list:
            cap = f"${m['market_cap']/1e9:.1f}B" if m["market_cap"] else "N/A"
            roe = f"{m['roe']:.1f}%"             if m["roe"] is not None else "N/A"
            eg  = f"{m['earnings_growth']:.1f}%" if m["earnings_growth"] is not None else "N/A"
            print(f"  {m['symbol']:<8} {cap:>10} {roe:>8} {eg:>11}  {m['sector']}")

    if failed_list:
        print(f"\nFailed tickers:")
        for sym, reasons in failed_list:
            print(f"  {sym}: {'; '.join(reasons)}")

    if error_list:
        print(f"\nSkipped (API errors): {', '.join(error_list)}")


if __name__ == "__main__":
    main()
