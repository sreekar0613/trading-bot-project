# Alpaca API Integration — Skill Documentation

## Overview
Alpaca is a commission-free stock brokerage with a developer-first API designed for algorithmic trading. Use for order execution, portfolio management, and historical market data retrieval.

**Official Docs**: https://docs.alpaca.markets/docs/

---

## Authentication

### API Keys
- **Paper Trading**: Separate keys for testing (unlimited fake money)
- **Live Trading**: Real money (requires funded account)

**Security Rules**:
- Store in `.env` file (never hardcode)
- Use environment variables: `os.getenv('ALPACA_API_KEY')`
- Add `.env` to `.gitignore`

### Python SDK Installation
```bash
pip install alpaca-py
```

### Initialization Example
```python
from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient
import os

# Trading client (orders, positions, account)
trading_client = TradingClient(
    api_key=os.getenv('ALPACA_API_KEY'),
    secret_key=os.getenv('ALPACA_SECRET_KEY'),
    paper=True  # False for live trading
)

# Data client (historical prices, no auth needed for free data)
data_client = StockHistoricalDataClient(
    api_key=os.getenv('ALPACA_API_KEY'),
    secret_key=os.getenv('ALPACA_SECRET_KEY')
)
```

---

## Key Endpoints

### 1. Account Information
**Purpose**: Check portfolio value, buying power, current P&L

**Endpoint**: `GET /v2/account`

```python
from alpaca.trading.requests import GetAccountRequest

account = trading_client.get_account()

print(f"Portfolio Value: ${account.portfolio_value}")
print(f"Buying Power: ${account.buying_power}")
print(f"Cash: ${account.cash}")
print(f"Equity: ${account.equity}")
print(f"Today's P&L: ${account.equity - account.last_equity}")
```

**Response Fields**:
- `portfolio_value` — Total account value (cash + positions)
- `buying_power` — Available capital for new trades
- `equity` — Current value of holdings
- `last_equity` — Yesterday's closing equity (for daily P&L calc)

---

### 2. Get Current Positions
**Purpose**: List all open positions (holdings)

**Endpoint**: `GET /v2/positions`

```python
positions = trading_client.get_all_positions()

for position in positions:
    print(f"{position.symbol}: {position.qty} shares @ ${position.avg_entry_price}")
    print(f"  Current Price: ${position.current_price}")
    print(f"  Unrealized P&L: ${position.unrealized_pl} ({position.unrealized_plpc}%)")
    print(f"  Market Value: ${position.market_value}")
```

**Response Fields**:
- `symbol` — Ticker (e.g., "AAPL")
- `qty` — Number of shares (fractional supported)
- `avg_entry_price` — Average cost basis
- `current_price` — Latest market price
- `unrealized_pl` — Profit/loss (not yet realized)
- `market_value` — Current position size ($)

---

### 3. Submit Market Order (Buy/Sell)
**Purpose**: Execute trades at current market price

**Endpoint**: `POST /v2/orders`

```python
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

# Buy order
buy_order = MarketOrderRequest(
    symbol="AAPL",
    qty=10.5,  # Fractional shares supported
    side=OrderSide.BUY,
    time_in_force=TimeInForce.DAY  # Cancel if not filled by market close
)

order = trading_client.submit_order(buy_order)
print(f"Order submitted: {order.id}")

# Sell order (close position)
sell_order = MarketOrderRequest(
    symbol="AAPL",
    qty=10.5,
    side=OrderSide.SELL,
    time_in_force=TimeInForce.DAY
)

trading_client.submit_order(sell_order)
```

**Time in Force Options**:
- `DAY` — Cancel at market close if not filled (recommended)
- `GTC` — Good till canceled (stays open indefinitely)
- `IOC` — Immediate or cancel (fill immediately or cancel)
- `FOK` — Fill or kill (all-or-nothing execution)

---

### 4. Submit Limit Order (Price Control)
**Purpose**: Only execute if price reaches specified level

```python
from alpaca.trading.requests import LimitOrderRequest

limit_order = LimitOrderRequest(
    symbol="AAPL",
    qty=10,
    side=OrderSide.BUY,
    time_in_force=TimeInForce.DAY,
    limit_price=150.00  # Only buy if price <= $150
)

trading_client.submit_order(limit_order)
```

**Use Case**: Avoid slippage during volatile periods (e.g., market open)

---

### 5. Cancel All Orders
**Purpose**: Emergency shutdown, clear pending orders

**Endpoint**: `DELETE /v2/orders`

```python
from alpaca.trading.requests import CancelOrdersRequest

trading_client.cancel_orders()  # Cancels ALL pending orders
print("All pending orders canceled")
```

**Use Case**: Part of kill switch logic (5% session loss trigger)

---

### 6. Close All Positions
**Purpose**: Exit all holdings immediately

**Endpoint**: `DELETE /v2/positions`

```python
trading_client.close_all_positions(cancel_orders=True)
print("All positions closed, pending orders canceled")
```

**Use Case**: Kill switch activation, emergency halt

---

### 7. Historical Market Data (OHLCV Bars)
**Purpose**: Fetch historical price data for backtesting

**Endpoint**: `GET /v2/stocks/{symbol}/bars`

```python
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime

request = StockBarsRequest(
    symbol_or_symbols=["AAPL", "MSFT"],
    timeframe=TimeFrame.Day,
    start=datetime(2020, 1, 1),
    end=datetime(2024, 12, 31)
)

bars = data_client.get_stock_bars(request)

# Convert to pandas DataFrame
df = bars.df

print(df.head())
# Output columns: open, high, low, close, volume, trade_count, vwap
```

**Timeframe Options**:
- `TimeFrame.Minute` — 1-minute bars
- `TimeFrame.Hour` — 1-hour bars
- `TimeFrame.Day` — Daily bars (recommended for this strategy)
- `TimeFrame.Week` — Weekly bars

**Rate Limits**: 200 requests/minute (free tier)

---

## Error Handling

### Common Errors

**1. Insufficient Buying Power**
```python
from alpaca.trading.requests import MarketOrderRequest
from alpaca.common.exceptions import APIError

try:
    order = trading_client.submit_order(MarketOrderRequest(...))
except APIError as e:
    if "insufficient buying power" in str(e).lower():
        print("ERROR: Not enough cash to execute trade")
    else:
        raise
```

**2. Market Closed**
```python
from alpaca.trading.requests import GetClockRequest

clock = trading_client.get_clock()

if not clock.is_open:
    print("Market is closed. Next open:", clock.next_open)
```

**3. Invalid Symbol**
```python
try:
    bars = data_client.get_stock_bars(request)
except APIError as e:
    if "symbol not found" in str(e).lower():
        print(f"ERROR: {symbol} is not a valid ticker")
```

---

## Rate Limits (Free Tier)

| Endpoint Type | Limit |
|---------------|-------|
| Trading (orders, positions) | 200 requests/minute |
| Market Data (bars, quotes) | 200 requests/minute |
| Account Info | 200 requests/minute |

**Best Practice**: Cache historical data locally (SQLite/PostgreSQL) to avoid repeated API calls

---

## Paper Trading vs Live Trading

### Paper Trading (Recommended for Testing)
- Free, unlimited "fake" money ($100,000 default)
- Same API, same endpoints, same order flow
- Real market data, real order fills (simulated)
- **No risk** — perfect for backtesting validation

**Base URL**: `https://paper-api.alpaca.markets`

### Live Trading
- Real money, real consequences
- Requires funded account
- Same code, just change `paper=False` and API keys

**Base URL**: `https://api.alpaca.markets`

**CRITICAL**: Never test unproven strategies with live keys

---

## Integration with Trading Bot

### Daily Signal Check (4:05 PM ET)
```python
import schedule
from datetime import datetime
import pytz

def check_signals():
    """Run after market close to calculate indicators on settled prices"""
    
    # Fetch today's closing prices
    request = StockBarsRequest(
        symbol_or_symbols=universe_tickers,
        timeframe=TimeFrame.Day,
        start=datetime.now() - timedelta(days=1),
        end=datetime.now()
    )
    
    bars = data_client.get_stock_bars(request)
    
    # Calculate RSI, MACD, Bollinger Bands, etc.
    signals = generate_signals(bars)
    
    # Queue orders for tomorrow morning
    for signal in signals:
        if signal['action'] == 'BUY':
            queue_buy_order(signal['symbol'], signal['qty'])

# Schedule for 4:05 PM ET daily
eastern = pytz.timezone('US/Eastern')
schedule.every().day.at("16:05").do(check_signals)

while True:
    schedule.run_pending()
    time.sleep(60)
```

### Order Execution (10:15 AM ET Next Day)
```python
def execute_queued_orders():
    """Submit orders after morning volatility settles"""
    
    clock = trading_client.get_clock()
    
    if not clock.is_open:
        print("Market closed, skipping execution")
        return
    
    for order in queued_orders:
        try:
            trading_client.submit_order(order)
            print(f"Executed: {order.symbol} {order.side} {order.qty}")
        except APIError as e:
            print(f"Order failed: {e}")

schedule.every().day.at("10:15").do(execute_queued_orders)
```

---

## Safety Mechanisms

### Kill Switch Implementation
```python
def check_session_loss():
    """Halt system if daily loss exceeds 5%"""
    
    account = trading_client.get_account()
    
    daily_pl = float(account.equity) - float(account.last_equity)
    daily_pl_pct = (daily_pl / float(account.last_equity)) * 100
    
    if daily_pl_pct < -5.0:
        print(f"KILL SWITCH TRIGGERED: {daily_pl_pct:.2f}% loss")
        
        # Emergency shutdown
        trading_client.cancel_orders()  # Cancel all pending
        trading_client.close_all_positions(cancel_orders=True)  # Exit all holdings
        
        # Send alert
        send_email_alert(f"Trading halted: {daily_pl_pct:.2f}% session loss")
        
        # Stop the bot
        exit(0)

# Check every 5 minutes during market hours
schedule.every(5).minutes.do(check_session_loss)
```

### Position Size Limits
```python
def validate_order(symbol, qty):
    """Ensure single position doesn't exceed 15% of portfolio"""
    
    account = trading_client.get_account()
    portfolio_value = float(account.portfolio_value)
    
    # Get current price
    bars = data_client.get_stock_bars(
        StockBarsRequest(
            symbol_or_symbols=[symbol],
            timeframe=TimeFrame.Day,
            start=datetime.now() - timedelta(days=1)
        )
    )
    
    latest_price = bars.df.iloc[-1]['close']
    position_value = qty * latest_price
    position_pct = (position_value / portfolio_value) * 100
    
    if position_pct > 15.0:
        print(f"ERROR: {symbol} would be {position_pct:.1f}% of portfolio (max 15%)")
        return False
    
    return True
```

---

## Testing Checklist

### Before Live Deployment
- [ ] API keys stored in `.env` (not hardcoded)
- [ ] Paper trading tested for 2+ weeks
- [ ] Orders execute at correct times (10:15 AM ET)
- [ ] Kill switch triggers at -5% daily loss
- [ ] Position size limits enforced (max 15%)
- [ ] Fractional shares working correctly
- [ ] Error handling catches API failures

---

## Useful References
- **SDK Docs**: https://alpaca.markets/docs/python-sdk/
- **API Reference**: https://docs.alpaca.markets/reference/
- **Market Calendar**: https://docs.alpaca.markets/docs/market-calendar (check for holidays)
- **Status Page**: https://status.alpaca.markets/ (monitor for outages)

---

## Common Pitfalls

1. **Forgetting `paper=True`** — Accidentally trading real money during testing
2. **Using GTC orders** — Orders stay open indefinitely, creating unexpected fills days later
3. **Not checking market hours** — Submitting orders when market is closed causes errors
4. **Ignoring rate limits** — Spamming API causes temporary bans
5. **Hardcoding API keys** — Security risk if code is shared or pushed to GitHub

---

## Next Steps
1. Create Alpaca account: https://alpaca.markets
2. Generate paper trading API keys
3. Test connection with `trading_client.get_account()`
4. Fetch sample historical data for AAPL (2020–2024)
5. Verify fractional shares work (submit 0.5 share test order)
