"""
Join liquid_universe + fundamental_universe and export a timestamped CSV report.

Output: reports/universe_summary_YYYYMMDD.csv
        reports/universe_summary.csv  (always overwritten — latest snapshot)

Usage:
    python data/generate_universe_report.py
"""

import csv
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT    = Path(__file__).resolve().parent.parent
DB_PATH      = REPO_ROOT / "trading_bot.db"
REPORTS_DIR  = REPO_ROOT / "reports"


QUERY = """
    SELECT
        lu.symbol,
        ROUND(lu.avg_volume_30d, 0)   AS avg_volume_90d,
        fu.market_cap,
        ROUND(fu.roe, 2)              AS roe,
        ROUND(fu.earnings_growth, 2)  AS earnings_growth,
        fu.sector,
        fu.last_updated
    FROM liquid_universe lu
    JOIN fundamental_universe fu ON fu.symbol = lu.symbol
    ORDER BY fu.market_cap DESC
"""

COLUMNS = ["symbol", "avg_volume_90d", "market_cap", "roe", "earnings_growth",
           "sector", "last_updated"]


def fetch_rows(conn: sqlite3.Connection) -> list[dict]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(QUERY).fetchall()
    return [dict(r) for r in rows]


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def sector_breakdown(rows: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["sector"] or "Unknown"] = counts.get(r["sector"] or "Unknown", 0) + 1
    return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))


def main() -> None:
    today     = datetime.now(timezone.utc)
    date_tag  = today.strftime("%Y%m%d")
    stamp     = today.strftime("%Y-%m-%d %H:%M UTC")

    conn = sqlite3.connect(DB_PATH)
    rows = fetch_rows(conn)
    conn.close()

    if not rows:
        print("No tickers found in both liquid_universe AND fundamental_universe.")
        print("Run screen_by_volume.py then fetch_fundamentals.py first.")
        return

    # Write timestamped + latest-snapshot files
    dated_path   = REPORTS_DIR / f"universe_summary_{date_tag}.csv"
    latest_path  = REPORTS_DIR / "universe_summary.csv"
    write_csv(rows, dated_path)
    write_csv(rows, latest_path)

    # ── Console summary ───────────────────────────────────────────────────────
    total      = len(rows)
    avg_roe    = sum(r["roe"] or 0 for r in rows) / total
    avg_cap_b  = sum((r["market_cap"] or 0) / 1e9 for r in rows) / total
    sectors    = sector_breakdown(rows)

    print(f"Universe Report — {stamp}")
    print(f"Database : {DB_PATH}")
    print()
    print(f"{'─'*52}")
    print(f"  Total qualified tickers : {total}")
    print(f"  Average ROE             : {avg_roe:.1f}%")
    print(f"  Average market cap      : ${avg_cap_b:.1f}B")
    print(f"{'─'*52}")

    print(f"\nSector breakdown:")
    for sector, count in sectors.items():
        bar = "█" * count
        print(f"  {sector:<20} {count:>3}  {bar}")

    print(f"\nQualified universe:")
    header = f"  {'Symbol':<8} {'Avg Vol (90d)':>14} {'Market Cap':>12} {'ROE':>7} {'EPS Gro':>8}  Sector"
    print(header)
    print(f"  {'─'*80}")
    for r in rows:
        vol  = f"{r['avg_volume_90d']:,.0f}"  if r["avg_volume_90d"]  else "N/A"
        cap  = f"${r['market_cap']/1e9:.1f}B" if r["market_cap"]      else "N/A"
        roe  = f"{r['roe']:.1f}%"             if r["roe"] is not None else "N/A"
        eg   = f"{r['earnings_growth']:.1f}%" if r["earnings_growth"] is not None else "N/A"
        print(f"  {r['symbol']:<8} {vol:>14} {cap:>12} {roe:>7} {eg:>8}  {r['sector']}")

    print(f"\nOutput files:")
    print(f"  {dated_path}")
    print(f"  {latest_path}  ← always latest")


if __name__ == "__main__":
    main()
