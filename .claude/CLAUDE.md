# Automated Trading Bot — Project Brief

## Mission
Build a fully autonomous trading system that analyzes real-time market data, executes trades without human intervention, and maintains a medium-risk/medium-growth profile (8–15% annual return target).

## Portfolio Parameters
- **Capital**: $1,100 (migrating from Robinhood to Alpaca)
- **Risk tolerance**: 5% session loss triggers complete system shutdown (~$55)
- **Hold period**: Medium-term (days to weeks, not intraday scalping)
- **Target positions**: 10–15 simultaneous holdings (diversification via fractional shares)

## Technology Stack
- **Broker**: Alpaca (official API, paper trading, commission-free, fractional shares)
- **Development**: VS Code + Claude Code (agentic coding with human-in-loop validation)
- **Backtesting**: `backtrader` or `vectorbt` + Alpaca historical data API
- **Data sources**: Finnhub (sentiment), Alpha Vantage (sentiment + fundamentals), Alpaca (price/volume)
- **Language**: Python 3.11+

## Core Strategy (Multi-Factor Confluence Model)

### 1. Fundamental Gatekeeping (Universe Selection)
**Purpose**: Filter tradable universe to quality stocks only — prevents trading garbage

| Filter | Threshold | Rationale |
|--------|-----------|-----------|
| Market Cap | > $2B | Institutional liquidity, stability |
| Avg Daily Volume | > 1M shares | Minimize slippage on entry/exit |
| Return on Equity (ROE) | > 15% | Management efficiency, competitive advantage |
| Price-to-Book (P/B) | < 2.0 | Reasonable valuation vs assets |
| Earnings Growth (YoY) | > 0% | Positive business momentum |

**Refresh frequency**: Weekly (Sunday after market close)

### 2. Technical Entry Signals (Confluence Required)
**Timeframe**: Daily close (check signals at 4:05 PM ET)

**Entry conditions (ALL must be true)**:
1. **Trend filter**: Price > 200-period EMA (only buy in uptrend)
2. **Oversold**: RSI(14) < 35
3. **Momentum confirmation**: MACD line crosses above signal line
4. **Volatility**: Price < Lower Bollinger Band * 1.01 (near lower bound)

**Additional checks**:
- Portfolio position count < 15
- Sector exposure < 25% of portfolio value
- 7-day rolling sentiment average > 0 (from Finnhub)

### 3. Position Sizing (Volatility-Adjusted)
**Formula**:
```
Risk_Amount = Account_Equity * 0.015  (1.5% risk per trade)
Stop_Distance = ATR(14) * 2.5
Share_Quantity = Risk_Amount / Stop_Distance

// Hard cap: single position cannot exceed 15% of portfolio
If (Share_Quantity * Price) > (Account_Equity * 0.15):
    Share_Quantity = (Account_Equity * 0.15) / Price
```

### 4. Exit Logic (Adaptive Risk Management)
**ATR Trailing Stop** (continuous monitoring):
```
Initial_Stop = Entry_Price - (2.5 * ATR(14))
Trailing_Stop = Max(Highest_Price_Since_Entry - (2.5 * ATR(14)), Initial_Stop)
```

**Exit triggers (ANY condition)**:
- Price drops below trailing stop
- RSI(14) > 65 (overbought, take profit)
- Hold time > 21 trading days (capital turnover)

### 5. Kill Switch Hierarchy (Multi-Level Protection)

| Level | Trigger | Action |
|-------|---------|--------|
| **Micro** (Trade) | Price < Trailing Stop | Close individual position |
| **Mezzo** (Daily) | Daily loss > 5% of equity | Cancel all orders, close all positions, halt system |
| **Macro** (Portfolio) | Drawdown > 15% from peak | Pause new entries for 48–72 hours |
| **Operational** | Orders > 10/minute | Emergency halt (API malfunction suspected) |

## Execution Protocols

### Trading Hours
- **Signal generation**: Daily at 4:05 PM ET (after close, settled prices)
- **Order execution**: Next day at 10:15 AM ET (avoid opening volatility 9:30–10:00 AM)
- **Avoid**: Last 30 minutes (3:30–4:00 PM ET) — high volatility, wide spreads

### Rebalancing
- **Frequency**: Weekly (Friday after close)
- **Purpose**: Adjust position sizes if any holding drifts > 15% concentration limit

### Sector Diversification
- No single GICS sector > 25% of portfolio value
- Prevents hidden correlation risk (e.g., 10 semiconductor stocks = single-sector exposure)

## Backtesting Requirements

### Validation Metrics (Must Pass)
| Metric | Target | Red Flag |
|--------|--------|----------|
| Sharpe Ratio | 1.0 – 1.8 | > 2.0 suggests overfitting |
| Max Drawdown | < 20% | > 25% unsustainable |
| Profit Factor | 1.5 – 2.0 | > 3.0 suggests curve-fitting |
| Win Rate | 45–60% | > 70% unrealistic |
| Recovery Factor | > 2.0 | Profit / Max Drawdown |

### Test Timeframe
- **Minimum**: 3 years of historical data
- **Critical period**: 2020–2024 (COVID crash, stimulus rally, 2022 bear market, 2023 AI rally)
- **Regime diversity**: Bull, bear, sideways markets

### Overfitting Red Flags
- Excessive parameters (> 6 indicators for single signal)
- Outlier dependence (majority of profit from 1–2 trades)
- Look-ahead bias (using future data in backtest logic)
- Ignoring frictions (slippage, commissions, spread costs)

## Data Pipeline Architecture

### APIs Required
1. **Alpaca** (trading execution + historical data)
   - `/v2/stocks/bars` — OHLCV price data
   - `/v2/account` — Portfolio value, buying power
   - `/v2/positions` — Current holdings
   - `/v2/orders` — Submit/cancel orders

2. **Finnhub** (sentiment analysis)
   - `/news-sentiment` — Company news sentiment scores
   - Rolling 7-day average, confidence-weighted

3. **Alpha Vantage** (fundamentals + backup sentiment)
   - `OVERVIEW` — Market cap, ROE, P/B ratio
   - `NEWS_SENTIMENT` — Alternative sentiment source

### Data Storage
- **PostgreSQL** or **SQLite** for local caching
- Tables: `price_history`, `sentiment_scores`, `fundamental_metrics`, `trade_log`, `portfolio_snapshots`
- Reduces API calls, enables offline backtesting

## 4-Phase Development Roadmap

### Phase 1: Data Pipeline + Fundamental Universe (Week 1)
**Deliverables**:
- Alpaca API connection (paper trading keys)
- Fetch historical OHLCV data (3 years, daily bars)
- Fundamental screener (market cap, ROE, P/B, volume filters)
- Output: CSV of qualified tickers (~50–200 stocks)

**Validation checkpoint**: Manually verify 10 random tickers meet all fundamental thresholds

---

### Phase 2: Backtesting Engine (Week 2–3)
**Deliverables**:
- `backtrader` or `vectorbt` environment setup
- Implement technical indicators (RSI, MACD, Bollinger Bands, EMA)
- Code entry/exit logic from pseudocode
- Run backtest on 2020–2024 data

**Validation checkpoint**: 
- Sharpe ratio 1.0–1.8
- Max drawdown < 20%
- Profit factor 1.5–2.0
- Visual equity curve + drawdown chart

**If metrics fail**: Adjust parameters (e.g., RSI threshold 30 → 35, ATR multiplier 2.0 → 2.5)

---

### Phase 3: Paper Trading (Week 4–7)
**Deliverables**:
- Deploy bot to Alpaca paper trading account
- Real-time data feeds (WebSocket or polling)
- Live signal generation (daily 4:05 PM ET)
- Order execution (next day 10:15 AM ET)
- Daily performance log

**Duration**: 2–4 weeks minimum

**Validation checkpoint**:
- Compare paper trading results to backtest expectations
- Monitor for execution bugs (slippage, failed orders, API errors)
- Verify kill switches trigger correctly (simulate 5% loss scenario)

---

### Phase 4: Live Deployment (Week 8+)
**Deliverables**:
- Migrate to live Alpaca account with $1,100 capital
- Enable all safety mechanisms (session loss limit, MDD pause)
- Implement logging/alerting (email/SMS on critical events)
- Weekly performance review (manual human oversight)

**Ongoing**:
- Monthly strategy review (check for regime shifts)
- Quarterly rebalancing of fundamental universe
- Annual backtest refresh (re-validate on new data)

---

## Critical Safety Constraints

### Pre-Flight Checklist (Before Live Deployment)
- [ ] Backtesting Sharpe ratio ≥ 1.0
- [ ] Paper trading ran ≥ 2 weeks without critical errors
- [ ] Kill switch tested (manual trigger + automatic 5% loss)
- [ ] API keys stored securely (environment variables, not hardcoded)
- [ ] No position can exceed 15% portfolio value
- [ ] No sector can exceed 25% portfolio value
- [ ] ATR trailing stops functional on all positions
- [ ] Order rate throttle prevents API spam (< 10 orders/minute)

### Monitoring Dashboard (Build in Phase 3)
**Real-time metrics**:
- Current portfolio value
- Daily P&L ($, %)
- Open positions (ticker, size, entry price, current P&L)
- Distance to session kill switch (5% - current loss)
- Distance to MDD pause (15% - current drawdown from peak)

**Weekly review metrics**:
- Win rate
- Average winner / average loser ratio
- Sharpe ratio (rolling 30-day)
- Sector exposure breakdown

---

## Development Workflow (Claude Code Integration)

### Prompt Template Structure
Each phase has modular prompts designed for Claude Code terminal:

**Format**:
```
CONTEXT: [Brief description of current phase]
TASK: [Specific coding objective]
REQUIREMENTS: [Technical specifications, API endpoints, validation criteria]
OUTPUT: [Expected files/functions/tests]
VALIDATION: [How to verify success]
```

### Validation Protocol
1. Paste prompt into Claude Code terminal
2. Claude Code generates code
3. You share output back to me (via copy-paste)
4. I review for logic errors, API misuse, security issues
5. If errors found: I provide corrected prompt
6. If correct: Move to next prompt in phase

### Error Handling
- All API calls wrapped in try/except with retry logic
- Fallback to cached data if API fails
- Log all errors to `error_log.txt` with timestamp
- Critical failures (e.g., kill switch trigger) send email alert

---

## API Key Management

### Environment Variables (Never Hardcode)
```bash
# .env file (add to .gitignore)
ALPACA_API_KEY=your_paper_key_here
ALPACA_SECRET_KEY=your_paper_secret_here
ALPACA_BASE_URL=https://paper-api.alpaca.markets
FINNHUB_API_KEY=your_finnhub_key
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_key
```

### Pre-Commit Hook (Add in Phase 1)
```bash
#!/bin/bash
# .git/hooks/pre-commit
if grep -r "ALPACA_API_KEY\s*=\s*['\"]" --exclude-dir=.git .; then
    echo "ERROR: API key detected in code. Use environment variables."
    exit 1
fi
```

---

## Code Structure (Final Architecture)

```
trading-bot/
├── .env                          # API keys (gitignored)
├── .gitignore
├── requirements.txt
├── config.py                     # Load env vars, global settings
├── data/
│   ├── fetch_historical.py       # Alpaca historical OHLCV
│   ├── fetch_fundamentals.py     # Alpha Vantage screener
│   ├── fetch_sentiment.py        # Finnhub sentiment scores
│   └── database.py               # SQLite/PostgreSQL interface
├── strategy/
│   ├── indicators.py             # RSI, MACD, Bollinger, EMA calculations
│   ├── signals.py                # Entry/exit logic
│   └── position_sizing.py        # ATR-based sizing, concentration limits
├── risk/
│   ├── stop_loss.py              # ATR trailing stop logic
│   ├── kill_switch.py            # Session loss, MDD pause
│   └── sector_limits.py          # 25% sector cap enforcement
├── execution/
│   ├── alpaca_trader.py          # Submit/cancel orders via API
│   └── scheduler.py              # Daily signal check (4:05 PM), order exec (10:15 AM)
├── backtesting/
│   ├── backtest_engine.py        # Backtrader/vectorbt runner
│   ├── performance_metrics.py    # Sharpe, drawdown, profit factor
│   └── equity_curve.py           # Plot results
├── live/
│   ├── bot.py                    # Main event loop
│   ├── monitor.py                # Dashboard/logging
│   └── alerts.py                 # Email/SMS notifications
└── tests/
    ├── test_indicators.py
    ├── test_signals.py
    └── test_risk_management.py
```

---

## Next Steps (Immediate)

1. **Create Alpaca account** (https://alpaca.markets)
   - Sign up for paper trading (free, instant)
   - Generate API keys (paper environment)
   - Save keys to `.env` file

2. **Create Finnhub account** (https://finnhub.io)
   - Free tier: 60 API calls/minute
   - Generate API key
   - Test `/company-news` endpoint

3. **Create Alpha Vantage account** (https://www.alphavantage.co)
   - Free tier: 25 API calls/day (may need premium for fundamentals)
   - Generate API key
   - Test `OVERVIEW` function

4. **Set up project directory**
   - Clone this `.claude` folder structure
   - Create virtual environment: `python -m venv venv`
   - Install dependencies: `pip install alpaca-py finnhub-python alpha-vantage backtrader pandas numpy`

5. **Ready for Phase 1 prompts**
   - I will provide specific Claude Code prompts for data pipeline
   - You paste into terminal, share outputs, I validate
   - Iterate until Phase 1 checkpoint passed

---

## Risk Disclaimers

- **No strategy guarantees profit** — backtesting performance ≠ future results
- **5% session loss limit** — protects against catastrophic failure, but drawdowns will occur
- **API failures possible** — broker downtime, rate limits, data feed errors can disrupt execution
- **Slippage on small account** — fractional shares help, but $110 positions still have impact cost
- **Human oversight required** — weekly performance review to catch regime shifts the model didn't predict

---

## Version History
- **v1.0** (Apr 2026) — Initial architecture, deferred insider trading data for Phase 2
