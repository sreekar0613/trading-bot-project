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
import ta

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH   = REPO_ROOT / "trading_bot.db"


# ── RSI ──────────────────────────────────────────────────────────────────────

def calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """
    Wilder's RSI (exponential smoothing, not simple average).
    """
    rsi_ind = ta.momentum.RSIIndicator(close=close, window=period)
    rsi = rsi_ind.rsi()
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
    macd_ind = ta.trend.MACD(close=close, window_slow=slow, window_fast=fast, window_sign=signal)
    
    return {
        "macd":      macd_ind.macd(),
        "signal":    macd_ind.macd_signal(),
        "histogram": macd_ind.macd_diff(),
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
    bb_ind = ta.volatility.BollingerBands(close=close, window=period, window_dev=std)

    return {
        "lower":  bb_ind.bollinger_lband(),
        "middle": bb_ind.bollinger_mavg(),
        "upper":  bb_ind.bollinger_hband(),
    }


# ── EMA ──────────────────────────────────────────────────────────────────────

def calculate_ema(close: pd.Series, period: int = 200) -> pd.Series:
    """
    Exponential Moving Average (trend filter).
    """
    ema_ind = ta.trend.EMAIndicator(close=close, window=period)
    return ema_ind.ema_indicator()


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
    atr_ind = ta.volatility.AverageTrueRange(high=high, low=low, close=close, window=period)
    return atr_ind.average_true_range()


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

    if df.empty:
        # Provide dummy data if DB is empty for quick testing
        np.random.seed(42)
        df = pd.DataFrame({
            'high': np.random.uniform(100, 110, 300),
            'low': np.random.uniform(90, 100, 300),
            'close': np.random.uniform(95, 105, 300)
        })

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
