"""
Vectorized technical indicator calculations for the trading bot strategy.

All functions accept pandas Series/DataFrame inputs and return Series or dicts
of Series with NaN-padded warm-up periods. No loops; all operations are vectorized.

Indicators implemented:
    RSI(14)          — entry: oversold < 35 | exit: overbought > 65
    MACD(12,26,9)    — entry: MACD crosses above signal
    Bollinger(20,2)  — entry: price near/below lower band
    EMA(200)         — trend filter: price must be above
    ATR(14)          — position sizing and trailing stop distance
"""

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import pandas_ta as ta

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH   = REPO_ROOT / "trading_bot.db"


# ── RSI ──────────────────────────────────────────────────────────────────────

def calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """
    Wilder's RSI (exponential smoothing, not simple average).
    """
    rsi = ta.rsi(close, length=period)
    if rsi is None:
        rsi = pd.Series(np.nan, index=close.index)
    return rsi


# ── MACD ─────────────────────────────────────────────────────────────────────

def calculate_macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> dict[str, pd.Series]:
    """
    MACD indicator.
    """
    macd_df = ta.macd(close, fast=fast, slow=slow, signal=signal)
    if macd_df is None or macd_df.empty:
        nan_series = pd.Series(np.nan, index=close.index)
        return {"macd": nan_series, "signal": nan_series, "histogram": nan_series}

    macd_line = macd_df[macd_df.columns[0]]
    histogram = macd_df[macd_df.columns[1]]
    signal_line = macd_df[macd_df.columns[2]]
    
    return {
        "macd":      macd_line,
        "signal":    signal_line,
        "histogram": histogram,
    }


# ── Bollinger Bands ───────────────────────────────────────────────────────────

def calculate_bollinger(
    close: pd.Series,
    period: int = 20,
    std: int = 2,
) -> dict[str, pd.Series]:
    """
    Bollinger Bands.
    """
    bb_df = ta.bbands(close, length=period, std=std)
    if bb_df is None or bb_df.empty:
        nan_series = pd.Series(np.nan, index=close.index)
        return {"upper": nan_series, "middle": nan_series, "lower": nan_series}

    return {
        "lower":  bb_df[bb_df.columns[0]],
        "middle": bb_df[bb_df.columns[1]],
        "upper":  bb_df[bb_df.columns[2]],
    }


# ── EMA ──────────────────────────────────────────────────────────────────────

def calculate_ema(close: pd.Series, period: int = 200) -> pd.Series:
    """
    Exponential Moving Average (trend filter).
    """
    ema = ta.ema(close, length=period)
    if ema is None:
        ema = pd.Series(np.nan, index=close.index)
    return ema


# ── ATR ──────────────────────────────────────────────────────────────────────

def calculate_atr(
    high:  pd.Series,
    low:   pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """
    Average True Range.
    """
    atr = ta.atr(high, low, close, length=period)
    if atr is None:
        atr = pd.Series(np.nan, index=close.index)
    return atr


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_price_history(symbol: str, db_path: Path = DB_PATH) -> pd.DataFrame:
    """Load OHLCV data from SQLite into a DataFrame indexed by date."""
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(
        "SELECT date, open, high, low, close, volume "
        "FROM price_history WHERE symbol = ? ORDER BY date",
        conn,
        params=(symbol,),
        parse_dates=["date"],
        index_col="date",
    )
    conn.close()
    return df


# ── Test block ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    SYMBOL = "AAPL"
    df = load_price_history(SYMBOL)

    rsi        = calculate_rsi(df["close"])
    macd_dict  = calculate_macd(df["close"])
    bb_dict    = calculate_bollinger(df["close"])
    ema200     = calculate_ema(df["close"], period=200)
    atr        = calculate_atr(df["high"], df["low"], df["close"])

    out = df[["close"]].copy()
    out["rsi"]        = rsi.round(2)
    out["macd"]       = macd_dict["macd"].round(4)
    out["macd_sig"]   = macd_dict["signal"].round(4)
    out["macd_hist"]  = macd_dict["histogram"].round(4)
    out["bb_upper"]   = bb_dict["upper"].round(2)
    out["bb_mid"]     = bb_dict["middle"].round(2)
    out["bb_lower"]   = bb_dict["lower"].round(2)
    out["ema200"]     = ema200.round(2)
    out["atr"]        = atr.round(4)

    print(f"\n{SYMBOL} — all indicators (last 5 rows)")
    print("=" * 100)
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 120)
    print(out.tail(5).to_string())

    # Quick sanity checks
    last = out.iloc[-1]
    print("\nSanity checks (last bar):")
    print(f"  RSI in [0,100]          : {0 <= last['rsi'] <= 100}")
    print(f"  BB lower < mid < upper  : {last['bb_lower'] < last['bb_mid'] < last['bb_upper']}")
    print(f"  ATR > 0                 : {last['atr'] > 0}")
    print(f"  EMA200 is a price       : {50 < last['ema200'] < 10_000}")
    print(f"  Total bars loaded       : {len(df)}")
    print(f"  NaN rows (warm-up end)  : RSI={rsi.isna().sum()}, EMA200={ema200.isna().sum()}, ATR={atr.isna().sum()}")
