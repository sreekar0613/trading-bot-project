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

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH   = REPO_ROOT / "trading_bot.db"


# ── RSI ──────────────────────────────────────────────────────────────────────

def calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """
    Wilder's RSI (exponential smoothing, not simple average).

    Parameters
    ----------
    close  : daily close prices
    period : lookback window (default 14)

    Returns
    -------
    pd.Series of RSI values in [0, 100]; NaN for first `period` rows.
    """
    delta = close.diff()
    gain  = delta.clip(lower=0)
    loss  = (-delta).clip(lower=0)

    # Wilder's smoothing = EWM with alpha = 1/period, adjust=False
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()

    rs  = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    # Mask the warm-up period so callers see explicit NaN, not pseudo-values
    rsi.iloc[:period] = np.nan
    return rsi


# ── MACD ─────────────────────────────────────────────────────────────────────

def calculate_macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> dict[str, pd.Series]:
    """
    MACD indicator (Gerald Appel, standard EMA formulation).

    Parameters
    ----------
    close  : daily close prices
    fast   : fast EMA period (default 12)
    slow   : slow EMA period (default 26)
    signal : signal line EMA period (default 9)

    Returns
    -------
    dict with keys:
        'macd'      — MACD line (fast EMA − slow EMA)
        'signal'    — signal line (EMA of MACD)
        'histogram' — MACD − signal
    """
    ema_fast    = close.ewm(span=fast,   adjust=False).mean()
    ema_slow    = close.ewm(span=slow,   adjust=False).mean()
    macd_line   = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()

    # Mask warm-up so callers have a clear NaN boundary
    macd_line.iloc[:slow - 1]              = np.nan
    signal_line.iloc[:slow - 1 + signal - 1] = np.nan

    return {
        "macd":      macd_line,
        "signal":    signal_line,
        "histogram": macd_line - signal_line,
    }


# ── Bollinger Bands ───────────────────────────────────────────────────────────

def calculate_bollinger(
    close: pd.Series,
    period: int = 20,
    std: int = 2,
) -> dict[str, pd.Series]:
    """
    Bollinger Bands (John Bollinger, standard SMA formulation).

    Parameters
    ----------
    close  : daily close prices
    period : SMA lookback window (default 20)
    std    : number of standard deviations for bands (default 2)

    Returns
    -------
    dict with keys:
        'upper'  — middle + std * rolling_std
        'middle' — SMA(period)
        'lower'  — middle − std * rolling_std
    """
    middle     = close.rolling(window=period).mean()
    rolling_sd = close.rolling(window=period).std(ddof=0)  # population std

    return {
        "upper":  middle + std * rolling_sd,
        "middle": middle,
        "lower":  middle - std * rolling_sd,
    }


# ── EMA ──────────────────────────────────────────────────────────────────────

def calculate_ema(close: pd.Series, period: int = 200) -> pd.Series:
    """
    Exponential Moving Average (trend filter).

    Parameters
    ----------
    close  : daily close prices
    period : EMA span (default 200)

    Returns
    -------
    pd.Series of EMA values; first `period − 1` rows are NaN.
    """
    ema = close.ewm(span=period, adjust=False).mean()
    ema.iloc[:period - 1] = np.nan
    return ema


# ── ATR ──────────────────────────────────────────────────────────────────────

def calculate_atr(
    high:  pd.Series,
    low:   pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """
    Average True Range (J. Welles Wilder, exponential smoothing).

    True Range = max(high−low, |high−prev_close|, |low−prev_close|)
    ATR        = Wilder's EWM of True Range (alpha = 1/period)

    The first row has no prior close, so TR[0] = high[0] − low[0].

    Parameters
    ----------
    high   : daily high prices
    low    : daily low prices
    close  : daily close prices
    period : ATR period (default 14)

    Returns
    -------
    pd.Series of ATR values; first `period` rows are NaN.
    """
    prev_close = close.shift(1)

    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low  - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    # Row 0: prev_close is NaN → TR defaults to high - low (correct)
    atr = tr.ewm(alpha=1 / period, adjust=False).mean()
    atr.iloc[:period] = np.nan
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
