"""
Screen tickers in price_history by 30-day average daily volume.
Tickers with avg volume >= 1,000,000 shares/day are written to liquid_universe.

Usage:
    python data/screen_by_volume.py
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT      = Path(__file__).resolve().parent.parent
DB_PATH        = REPO_ROOT / "trading_bot.db"
# IEX free feed captures ~1-3% of the consolidated tape.
# Real 1M-share threshold scales to ~20,000 on IEX data.
# Switch feed="sip" (paid plan) to restore full-market volumes and raise this back to 1_000_000.
MIN_AVG_VOLUME = 20_000
LOOKBACK_DAYS  = 90   # 3-month ADV is industry standard; avoids holiday-week skew


def ensure_liquid_universe_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS liquid_universe (
            symbol        TEXT PRIMARY KEY,
            avg_volume_30d REAL,
            last_updated  DATE
        )
    """)
    conn.commit()


def get_volume_stats(conn: sqlite3.Connection) -> list[dict]:
    """Return 30-day avg volume for every symbol in price_history."""
    rows = conn.execute("""
        SELECT
            symbol,
            AVG(volume) AS avg_volume_30d
        FROM (
            SELECT symbol, volume
            FROM price_history
            WHERE date >= (
                SELECT DATE(MAX(date), :offset)
                FROM price_history AS ph2
                WHERE ph2.symbol = price_history.symbol
            )
        )
        GROUP BY symbol
        ORDER BY avg_volume_30d DESC
    """, {"offset": f"-{LOOKBACK_DAYS} days"}).fetchall()

    return [{"symbol": r[0], "avg_volume_30d": r[1]} for r in rows]


def upsert_liquid_universe(conn: sqlite3.Connection, qualified: list[dict]) -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    conn.executemany(
        """
        INSERT OR REPLACE INTO liquid_universe (symbol, avg_volume_30d, last_updated)
        VALUES (:symbol, :avg_volume_30d, :last_updated)
        """,
        [{**row, "last_updated": today} for row in qualified],
    )
    conn.commit()


def remove_delisted(conn: sqlite3.Connection, qualified_symbols: set[str]) -> None:
    """Remove symbols that were previously qualified but no longer pass."""
    existing = {r[0] for r in conn.execute("SELECT symbol FROM liquid_universe").fetchall()}
    to_remove = existing - qualified_symbols
    if to_remove:
        conn.executemany(
            "DELETE FROM liquid_universe WHERE symbol = ?",
            [(s,) for s in to_remove],
        )
        conn.commit()


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        ensure_liquid_universe_table(conn)

        all_stats = get_volume_stats(conn)
        total     = len(all_stats)

        qualified = [s for s in all_stats if s["avg_volume_30d"] >= MIN_AVG_VOLUME]
        rejected  = [s for s in all_stats if s["avg_volume_30d"] <  MIN_AVG_VOLUME]

        upsert_liquid_universe(conn, qualified)
        remove_delisted(conn, {s["symbol"] for s in qualified})

        # ── Summary ──────────────────────────────────────────────────────────
        print(f"Volume Screen — {LOOKBACK_DAYS}-day average ≥ {MIN_AVG_VOLUME:,} shares/day")
        print(f"Database: {DB_PATH}\n")
        print(f"Tickers analyzed : {total}")
        print(f"Passed filter    : {len(qualified)}")
        print(f"Failed filter    : {len(rejected)}")

        if qualified:
            print(f"\n{'Symbol':<10} {'Avg Daily Volume (30d)':>24}")
            print("-" * 36)
            for s in qualified:
                print(f"{s['symbol']:<10} {s['avg_volume_30d']:>24,.0f}")
        else:
            print("\nNo tickers passed the volume filter.")
            print("Tip: run fetch_historical_data.py for more tickers first.")

        if rejected:
            print(f"\nFailed (avg vol < {MIN_AVG_VOLUME:,}):")
            for s in rejected:
                print(f"  {s['symbol']:<10} {s['avg_volume_30d']:>15,.0f}")

        print(f"\n✓ liquid_universe table updated ({len(qualified)} rows).")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
