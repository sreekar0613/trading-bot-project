"""
Defensive initializer for the liquid_universe table.

Safe to run at any time — creates the table if absent and seeds it from
reports/universe_summary.csv if empty. Idempotent: does nothing when
the table already has rows.
"""

import csv
import logging
import sqlite3
from datetime import date
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT      = Path(__file__).resolve().parent.parent
DB_PATH   = ROOT / "trading_bot.db"
CSV_PATH  = ROOT / "reports" / "universe_summary.csv"
LOG_FILE  = ROOT / "logs" / "paper_trading.log"

LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("init_liquid_universe")

# ── DDL ────────────────────────────────────────────────────────────────────────
_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS liquid_universe (
    symbol         TEXT PRIMARY KEY,
    avg_volume_30d REAL,
    last_updated   TEXT
)
"""


def ensure_table(conn: sqlite3.Connection) -> bool:
    """Create table if absent. Returns True if it had to be created."""
    before = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='liquid_universe'"
    ).fetchone()
    conn.execute(_CREATE_SQL)
    conn.commit()
    created = before is None
    if created:
        log.info("liquid_universe table created.")
    return created


def row_count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM liquid_universe").fetchone()[0]


def seed_from_csv(conn: sqlite3.Connection) -> int:
    """Insert rows from universe_summary.csv. Returns number of rows inserted."""
    if not CSV_PATH.exists():
        log.error("Seed file not found: %s", CSV_PATH)
        raise FileNotFoundError(CSV_PATH)

    today = date.today().isoformat()
    inserted = 0

    with open(CSV_PATH, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            symbol = row.get("symbol", "").strip()
            # CSV column is avg_volume_90d; stored as avg_volume_30d to match table schema
            raw_vol = row.get("avg_volume_90d") or row.get("avg_volume_30d", "0")
            try:
                avg_vol = float(raw_vol)
            except ValueError:
                log.warning("Skipping %s — bad volume value: %r", symbol, raw_vol)
                continue

            conn.execute(
                "INSERT OR IGNORE INTO liquid_universe (symbol, avg_volume_30d, last_updated) "
                "VALUES (?, ?, ?)",
                (symbol, avg_vol, today),
            )
            inserted += conn.execute(
                "SELECT changes()"
            ).fetchone()[0]

    conn.commit()
    return inserted


def init() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        ensure_table(conn)

        count = row_count(conn)
        if count > 0:
            log.info(
                "liquid_universe already initialized (%d rows). Nothing to do.", count
            )
            return

        log.info("liquid_universe is empty — seeding from %s", CSV_PATH.name)
        n = seed_from_csv(conn)
        final = row_count(conn)
        log.info("Seeded %d row(s). liquid_universe now has %d row(s).", n, final)

    except Exception as exc:
        log.error("init_liquid_universe failed: %s", exc)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    init()
