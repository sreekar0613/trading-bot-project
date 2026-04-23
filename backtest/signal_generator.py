"""
Signal generation for the multi-factor trading strategy.

Entry (ALL conditions must be true on the same bar):
    1. RSI(14)      < 35           — oversold
    2. MACD hist    > 0            — bullish momentum
    3. MACD hist[t-1] <= 0         — crossover just occurred (new signal only)
    4. Close        < Lower Bollinger Band(20,2)
    5. Close        > EMA(200)     — uptrend filter

Exit (ANY condition triggers close):
    A. RSI(14)      > 65           — overbought, take profit
    B. Calendar days since entry   > 21   — max hold period
    C. Close        < trailing stop        — ATR-based trailing stop

Trailing stop formula (from CLAUDE.md):
    initial_stop    = entry_price − 2.5 × ATR_at_entry
    trailing_stop   = max(peak_since_entry − 2.5 × current_ATR, initial_stop)

Exit logic is stateful: only evaluated while a position is open.
One position per ticker at a time; overlapping entries are skipped.
"""

import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from indicators.technical import (
    calculate_atr,
    calculate_bollinger,
    calculate_ema,
    calculate_macd,
    calculate_rsi,
    load_price_history,
)

DB_PATH = REPO_ROOT / "trading_bot.db"

# ── Strategy parameters ───────────────────────────────────────────────────────
RSI_ENTRY        = 35
RSI_EXIT         = 65
ATR_MULTIPLIER   = 2.5
MAX_HOLD_DAYS    = 21   # calendar days


# ── Core signal generator ─────────────────────────────────────────────────────

def generate_signals(
    symbol: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """
    Generate entry and exit signals for one ticker over a date range.

    Loads OHLCV from trading_bot.db, computes all five indicators, then
    walks the time series forward to track open position state. Entry is
    only generated when no position is open; exit is only evaluated while
    a position is open.

    Parameters
    ----------
    symbol     : ticker symbol (must exist in price_history)
    start_date : inclusive start, e.g. '2020-07-01'
    end_date   : inclusive end,   e.g. '2024-12-31'

    Returns
    -------
    pd.DataFrame with columns:
        date, symbol, signal_type, price, atr, reason
    Returns empty DataFrame if no signals generated.
    """
    df = load_price_history(symbol)
    df = df.loc[start_date:end_date]

    if len(df) < 210:   # not enough bars for EMA(200) to be meaningful
        return _empty_signals()

    # ── Compute indicators ────────────────────────────────────────────────────
    df = df.copy()
    df["rsi"]       = calculate_rsi(df["close"])
    macd            = calculate_macd(df["close"])
    df["macd_hist"] = macd["histogram"]
    bb              = calculate_bollinger(df["close"])
    df["bb_lower"]  = bb["lower"]
    df["ema200"]    = calculate_ema(df["close"], period=200)
    df["atr"]       = calculate_atr(df["high"], df["low"], df["close"])

    # Drop any rows where a required indicator is NaN (warm-up period)
    required = ["rsi", "macd_hist", "bb_lower", "ema200", "atr"]
    df = df.dropna(subset=required)

    # ── State tracking ────────────────────────────────────────────────────────
    signals: list[dict] = []

    in_position      = False
    entry_date       = None
    entry_price      = None
    initial_stop     = None
    peak_since_entry = None

    dates  = df.index.to_list()
    n      = len(dates)

    for i, date in enumerate(dates):
        row      = df.loc[date]
        close    = row["close"]
        atr      = row["atr"]
        rsi      = row["rsi"]
        hist     = row["macd_hist"]
        bb_lower = row["bb_lower"]
        ema200   = row["ema200"]

        # Need previous histogram for crossover detection
        prev_hist = df["macd_hist"].iloc[i - 1] if i > 0 else np.nan

        if in_position:
            # ── Update peak ───────────────────────────────────────────────────
            peak_since_entry = max(peak_since_entry, close)

            # ── Trailing stop ─────────────────────────────────────────────────
            trailing_stop = max(
                peak_since_entry - ATR_MULTIPLIER * atr,
                initial_stop,
            )

            # ── Check exit conditions ─────────────────────────────────────────
            hold_days     = (date - entry_date).days
            rsi_exit      = rsi > RSI_EXIT
            time_exit     = hold_days > MAX_HOLD_DAYS
            stop_exit     = close < trailing_stop

            if rsi_exit or time_exit or stop_exit:
                reasons = []
                if rsi_exit:
                    reasons.append(f"RSI {rsi:.1f} > {RSI_EXIT}")
                if time_exit:
                    reasons.append(f"{hold_days}d hold > {MAX_HOLD_DAYS}d limit")
                if stop_exit:
                    reasons.append(
                        f"Trailing stop hit (stop={trailing_stop:.2f}, "
                        f"close={close:.2f}, peak={peak_since_entry:.2f})"
                    )

                signals.append({
                    "date":        date,
                    "symbol":      symbol,
                    "signal_type": "exit",
                    "price":       close,
                    "atr":         round(atr, 4),
                    "reason":      "Exit: " + "; ".join(reasons),
                })
                in_position = False
                entry_date  = entry_price = initial_stop = peak_since_entry = None

        else:
            # ── Check entry conditions ────────────────────────────────────────
            rsi_ok       = rsi       < RSI_ENTRY
            macd_cross   = (hist > 0) and (not np.isnan(prev_hist)) and (prev_hist <= 0)
            bb_ok        = close     < bb_lower
            ema_ok       = close     > ema200

            if rsi_ok and macd_cross and bb_ok and ema_ok:
                initial_stop     = close - ATR_MULTIPLIER * atr
                peak_since_entry = close
                entry_date       = date
                entry_price      = close
                in_position      = True

                signals.append({
                    "date":        date,
                    "symbol":      symbol,
                    "signal_type": "entry",
                    "price":       close,
                    "atr":         round(atr, 4),
                    "reason": (
                        f"Entry: RSI {rsi:.1f}, MACD cross ({prev_hist:.4f}→{hist:.4f}), "
                        f"price {close:.2f} < BB-lower {bb_lower:.2f}, "
                        f"EMA200 {ema200:.2f}"
                    ),
                })

    if not signals:
        return _empty_signals()

    return pd.DataFrame(signals).set_index("date")


def _empty_signals() -> pd.DataFrame:
    cols = ["symbol", "signal_type", "price", "atr", "reason"]
    return pd.DataFrame(columns=cols, index=pd.DatetimeIndex([], name="date"))


# ── Universe scanner ──────────────────────────────────────────────────────────

def scan_universe(
    start_date: str = "2020-07-01",
    end_date:   str = "2024-12-31",
) -> pd.DataFrame:
    """
    Run generate_signals() for every ticker in fundamental_universe and
    return a single signal log sorted by date.

    Parameters
    ----------
    start_date : inclusive start date string
    end_date   : inclusive end date string

    Returns
    -------
    pd.DataFrame with the same columns as generate_signals(), sorted by date.
    """
    conn    = sqlite3.connect(DB_PATH)
    tickers = [
        r[0]
        for r in conn.execute(
            "SELECT symbol FROM fundamental_universe ORDER BY symbol"
        ).fetchall()
    ]
    conn.close()

    all_signals: list[pd.DataFrame] = []
    for symbol in tickers:
        sig = generate_signals(symbol, start_date, end_date)
        if not sig.empty:
            all_signals.append(sig)
        print(f"  {symbol}: {len(sig)} signals")

    if not all_signals:
        return _empty_signals()

    combined = pd.concat(all_signals).sort_index()
    return combined


# ── Test block ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    START = "2020-07-01"
    END   = "2024-12-31"

    print(f"Signal Generator — {START} to {END}")
    print("=" * 70)
    print("\nScanning universe …")
    signals = scan_universe(START, END)

    if signals.empty:
        print("\nNo signals generated. Strategy conditions may be too strict.")
        sys.exit(0)

    entries = signals[signals["signal_type"] == "entry"]
    exits   = signals[signals["signal_type"] == "exit"]

    print(f"\n{'─'*70}")
    print(f"  Total signals : {len(signals)}")
    print(f"  Entries       : {len(entries)}")
    print(f"  Exits         : {len(exits)}")
    print(f"{'─'*70}")

    # ── Per-ticker breakdown ──────────────────────────────────────────────────
    print("\nPer-ticker signal count:")
    ticker_counts = (
        signals.groupby(["symbol", "signal_type"])
        .size()
        .unstack(fill_value=0)
        .reindex(columns=["entry", "exit"], fill_value=0)
    )
    print(ticker_counts.to_string())

    # ── Exit reason breakdown ─────────────────────────────────────────────────
    def classify_exit(reason: str) -> str:
        if "RSI"      in reason: return "RSI overbought"
        if "hold"     in reason: return "21-day time exit"
        if "Trailing" in reason: return "Trailing stop"
        return "Other"

    if not exits.empty:
        exits_copy = exits.copy()
        exits_copy["exit_type"] = exits_copy["reason"].map(classify_exit)
        print("\nExit reason breakdown:")
        print(exits_copy["exit_type"].value_counts().to_string())

    # ── All signals table ─────────────────────────────────────────────────────
    print(f"\nAll signals (sorted by date):")
    print(f"{'─'*70}")
    pd.set_option("display.max_colwidth", 90)
    pd.set_option("display.width", 120)
    print(signals[["symbol", "signal_type", "price", "atr", "reason"]].to_string())
