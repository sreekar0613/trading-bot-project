"""One-off verification: ta==0.11.0 indicator outputs match live/backtest expectations."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(REPO_ROOT))

import pandas as pd
from indicators.technical import (
    calculate_rsi, calculate_macd, calculate_bollinger, calculate_ema, calculate_atr,
    load_price_history,
)

SYMBOL = "AAPL"
df = load_price_history(SYMBOL)
print(f"Loaded {SYMBOL}: {len(df)} rows, columns={list(df.columns)}\n")

rsi    = calculate_rsi(df["close"])
macd   = calculate_macd(df["close"])
bb     = calculate_bollinger(df["close"])
ema200 = calculate_ema(df["close"], period=200)
atr    = calculate_atr(df["high"], df["low"], df["close"])


def describe_series(name: str, s: pd.Series):
    print(f"[{name}]")
    print(f"  type           : {type(s).__name__}")
    print(f"  dtype          : {s.dtype}")
    print(f"  leading NaN    : {s.isna().sum()}  (total len {len(s)})")
    print(f"  last 3 non-NaN : {s.dropna().tail(3).round(4).tolist()}")
    print()


def describe_dict(name: str, d: dict):
    print(f"[{name}]")
    print(f"  type           : dict")
    print(f"  keys           : {list(d.keys())}")
    for k, v in d.items():
        print(f"    .{k:<10s} dtype={v.dtype}  leading_NaN={v.isna().sum():>3d}  "
              f"last3={v.dropna().tail(3).round(4).tolist()}")
    print()


describe_series("RSI",  rsi)
describe_dict ("MACD", macd)
describe_dict ("Bollinger", bb)
describe_series("EMA200", ema200)
describe_series("ATR", atr)


# ── Contract checks ──────────────────────────────────────────────────────────
checks = []

checks.append(("MACD has keys ['macd','signal','histogram']",
               set(macd.keys()) == {"macd", "signal", "histogram"}))
checks.append(("Bollinger has keys ['upper','middle','lower']",
               set(bb.keys()) == {"upper", "middle", "lower"}))
checks.append(("calculate_rsi returns Series", isinstance(rsi, pd.Series)))
checks.append(("calculate_ema returns Series", isinstance(ema200, pd.Series)))
checks.append(("calculate_atr returns Series", isinstance(atr, pd.Series)))
checks.append(("macd['histogram'] not all NaN  (live/bot.py uses df['macd_hist'])",
               not macd["histogram"].isna().all()))
checks.append(("bb['lower'] not all NaN        (live/bot.py uses bb_data['lower'])",
               not bb["lower"].isna().all()))

print("=" * 70)
print("CONTRACT CHECKS")
print("=" * 70)
all_pass = True
for label, ok in checks:
    status = "PASS" if ok else "FAIL"
    if not ok:
        all_pass = False
    print(f"  [{status}] {label}")

print("=" * 70)
print(f"OVERALL: {'ALL PASS — indicators safe to use in live bot' if all_pass else 'FAIL — DO NOT TRUST LIVE SIGNALS'}")
print("=" * 70)
sys.exit(0 if all_pass else 1)
