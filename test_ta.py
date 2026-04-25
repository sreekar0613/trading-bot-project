import pandas as pd
import numpy as np
import ta

np.random.seed(42)
df = pd.DataFrame({
    'high': np.random.uniform(100, 110, 300),
    'low': np.random.uniform(90, 100, 300),
    'close': np.random.uniform(95, 105, 300)
})

# RSI
rsi_ind = ta.momentum.RSIIndicator(close=df['close'], window=14)
print("RSI:", rsi_ind.rsi().iloc[-1])

# MACD
macd_ind = ta.trend.MACD(close=df['close'], window_slow=26, window_fast=12, window_sign=9)
print("MACD:", macd_ind.macd().iloc[-1])
print("MACD signal:", macd_ind.macd_signal().iloc[-1])
print("MACD diff:", macd_ind.macd_diff().iloc[-1])

# Bollinger Bands
bb_ind = ta.volatility.BollingerBands(close=df['close'], window=20, window_dev=2)
print("BB high:", bb_ind.bollinger_hband().iloc[-1])
print("BB mid:", bb_ind.bollinger_mavg().iloc[-1])
print("BB low:", bb_ind.bollinger_lband().iloc[-1])

# EMA
ema_ind = ta.trend.EMAIndicator(close=df['close'], window=200)
print("EMA:", ema_ind.ema_indicator().iloc[-1])

# ATR
atr_ind = ta.volatility.AverageTrueRange(high=df['high'], low=df['low'], close=df['close'], window=14)
print("ATR:", atr_ind.average_true_range().iloc[-1])

