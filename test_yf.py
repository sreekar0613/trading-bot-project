import yfinance as yf
import pandas as pd

tickers = ['AAPL', 'MSFT']
df = yf.download(tickers, start='2023-01-01', end='2023-01-10')
print("Multi ticker shape:", df.shape)
try:
    df = df.stack(level=1, future_stack=True)
except TypeError:
    df = df.stack(level=1)
df.index.names = ['timestamp', 'symbol']
df = df.swaplevel(0, 1)
df.columns = [c.lower() for c in df.columns]
print(df.head())

tickers = ['AAPL']
df = yf.download(tickers, start='2023-01-01', end='2023-01-10')
print("Single ticker shape:", df.shape)
if isinstance(df.columns, pd.MultiIndex):
    try:
        df = df.stack(level=1, future_stack=True)
    except TypeError:
        df = df.stack(level=1)
    df.index.names = ['timestamp', 'symbol']
    df = df.swaplevel(0, 1)
else:
    df['symbol'] = tickers[0]
    df = df.set_index('symbol', append=True)
    df = df.swaplevel(0, 1)
    df.index.names = ['symbol', 'timestamp']
df.columns = [str(c).lower() for c in df.columns]
print(df.head())
