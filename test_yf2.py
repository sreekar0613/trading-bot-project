import yfinance as yf
import pandas as pd
tickers = ['AAPL']
df = yf.download(tickers, start='2023-01-01', end='2023-01-10')
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

print("tz:", df.index.levels[1].tz)
if df.index.levels[1].tz is None:
    df.index = df.index.set_levels(df.index.levels[1].tz_localize('UTC'), level=1)
else:
    df.index = df.index.set_levels(df.index.levels[1].tz_convert('UTC'), level=1)
print("new tz:", df.index.levels[1].tz)
