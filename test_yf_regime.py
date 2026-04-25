import yfinance as yf
import pandas as pd

df = yf.download(['SPY', '^VIX'], period="1y", progress=False)
print(df.columns)
if 'Close' in df.columns:
    spy_close = df['Close']['SPY'].iloc[-1]
    vix_close = df['Close']['^VIX'].iloc[-1]
    spy_ema200 = df['Close']['SPY'].ewm(span=200, adjust=False).mean().iloc[-1]
    print(spy_close, vix_close, spy_ema200)
else:
    print("Close not found")
