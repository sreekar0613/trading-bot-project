"""Seed extended tickers into fundamental_universe with placeholder fundamentals.

Backtest-only helper: ensures the signal generator considers a wider ticker set.
Uses INSERT OR IGNORE so existing real fundamentals are preserved.
"""
from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "trading_bot.db"

EXTENDED = [
    ("AMZN", "Consumer Cyclical"),
    ("TSLA", "Consumer Cyclical"),
    ("NFLX", "Communication Services"),
    ("AMD", "Technology"),
    ("INTC", "Technology"),
    ("CRM", "Technology"),
    ("ORCL", "Technology"),
    ("COST", "Consumer Defensive"),
    ("HD", "Consumer Cyclical"),
    ("UNH", "Healthcare"),
    ("JNJ", "Healthcare"),
    ("PG", "Consumer Defensive"),
    ("XOM", "Energy"),
    ("BAC", "Financial Services"),
    ("WFC", "Financial Services"),
    ("GS", "Financial Services"),
    ("MA", "Financial Services"),
    ("DIS", "Communication Services"),
    ("ADBE", "Technology"),
    ("QCOM", "Technology"),
]

PLACEHOLDER_MARKET_CAP = 500_000_000_000.0
PLACEHOLDER_ROE = 20.0
PLACEHOLDER_EARNINGS_GROWTH = 10.0


def main() -> None:
    today = date.today().isoformat()
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        inserted = 0
        for symbol, sector in EXTENDED:
            cur.execute(
                """INSERT OR IGNORE INTO fundamental_universe
                   (symbol, market_cap, roe, sector, earnings_growth, last_updated)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (symbol, PLACEHOLDER_MARKET_CAP, PLACEHOLDER_ROE,
                 sector, PLACEHOLDER_EARNINGS_GROWTH, today),
            )
            if cur.rowcount > 0:
                inserted += 1
                print(f"  inserted {symbol} ({sector})")
            else:
                print(f"  skipped  {symbol} (already present)")
        conn.commit()
        total = cur.execute("SELECT COUNT(*) FROM fundamental_universe").fetchone()[0]
        print(f"\nNew rows inserted: {inserted}")
        print(f"Total rows in fundamental_universe: {total}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
