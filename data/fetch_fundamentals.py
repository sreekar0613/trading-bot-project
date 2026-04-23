import os
import sys
import sqlite3
import logging
from datetime import datetime, timezone
from pathlib import Path
import yfinance as yf

# Configuration
REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH   = REPO_ROOT / "trading_bot.db"

# Setup logging
LOG_FILE = REPO_ROOT / "logs" / "paper_trading.log"
os.makedirs(LOG_FILE.parent, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stdout)]
)

# ── Watchlist override ───────────────────────────────────────────────────────
WATCHLIST: list[str] = [
    "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "TSLA", "BRK.B", "UNH", "LLY",
    "JPM", "V", "JNJ", "XOM", "PG", "MA", "AVGO", "HD", "CVX", "MRK",
    "PEP", "COST", "ABBV", "KO", "BAC", "CRM", "ORCL", "MCD", "TMO", "CSCO",
    "ACN", "INTC", "DHR", "ABT", "NFLX", "CMCSA", "AMD", "TMUS", "WFC", "DIS",
    "TXN", "PM", "COP", "LIN", "NKE", "AXP", "AMGN", "QCOM", "CAT", "BA"
]

MIN_MARKET_CAP_B = 2.0
MIN_ROE_PCT      = 15.0

def get_liquid_tickers(conn: sqlite3.Connection) -> list[str]:
    try:
        rows = conn.execute("SELECT symbol FROM liquid_universe ORDER BY symbol").fetchall()
        return [r[0] for r in rows]
    except sqlite3.OperationalError:
        return []

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
    conn = sqlite3.connect(DB_PATH)

    tickers = WATCHLIST if WATCHLIST else get_liquid_tickers(conn)
    if not tickers:
        print("Watchlist and liquid_universe are empty.")
        conn.close()
        sys.exit(0)

    print("Fundamental Screener — Yahoo Finance")
    print(f"Database : {DB_PATH}")
    print(f"Filters  : MarketCap > ${MIN_MARKET_CAP_B}B | ROE > {MIN_ROE_PCT}%\n")

    passed_list = []
    failed_list = []

    for idx, symbol in enumerate(tickers):
        print(f"[{idx+1}/{len(tickers)}] Fetching {symbol}...")
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            if not info or "symbol" not in info and "shortName" not in info:
                print(f"  -> WARNING: {symbol} returned empty or invalid data. Skipping.")
                failed_list.append((symbol, ["Invalid or empty response"]))
                continue

            market_cap = info.get('marketCap', 0)
            roe = info.get('returnOnEquity', 0)
            if roe is not None:
                roe *= 100 # Convert to percentage
            else:
                roe = 0

            sector = info.get('sector', 'Unknown')
            earnings_growth = info.get('earningsGrowth', 0)
            if earnings_growth is not None:
                earnings_growth *= 100
            else:
                earnings_growth = 0

            mktCap_b = market_cap / 1e9 if market_cap else 0
            
            failures = []
            if mktCap_b <= MIN_MARKET_CAP_B:
                failures.append(f"Market cap ${mktCap_b:.2f}B <= ${MIN_MARKET_CAP_B}B")
                
            # Optional: Add ROE check if we strictly enforce it here 
            # (Assuming we do since it's a fundamental filter requirement)
            if roe <= MIN_ROE_PCT:
                failures.append(f"ROE {roe:.1f}% <= {MIN_ROE_PCT}%")

            cap_str = f"${mktCap_b:.2f}B" if market_cap else "N/A"
            print(f"  MarketCap={cap_str}  ROE={roe:.1f}%  Sector={sector}")

            metrics = {
                "symbol": symbol,
                "market_cap": market_cap,
                "roe": roe,
                "sector": sector,
                "earnings_growth": earnings_growth,
            }

            if not failures:
                upsert_fundamental_universe(conn, metrics)
                passed_list.append(metrics)
                print(f"  -> PASSED ✓\n")
            else:
                failed_list.append((symbol, failures))
                print(f"  -> FAILED: {'; '.join(failures)}\n")

        except Exception as e:
            print(f"  -> WARNING: Failed to fetch data for {symbol}: {e}")
            failed_list.append((symbol, [f"Exception: {e}"]))
            continue

    conn.close()

    print("=" * 60)
    print(f"SUMMARY")
    print(f"  Analyzed : {len(tickers)}")
    print(f"  Passed   : {len(passed_list)}")
    print(f"  Failed   : {len(failed_list)}")

if __name__ == "__main__":
    main()