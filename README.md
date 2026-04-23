# Automated Trading Bot

Fully autonomous trading system using multi-factor analysis (technical + fundamental + sentiment) with adaptive risk management.

**Target**: 8–15% annual return, medium risk profile  
**Capital**: $1,100 starting portfolio  
**Broker**: Alpaca (paper trading → live deployment)

---

## Quick Start

### 1. Prerequisites
- Python 3.11+
- API accounts: Alpaca, Finnhub, Alpha Vantage

### 2. Installation
```bash
# Clone repository
git clone <repo-url>
cd trading-bot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration
Create `.env` file in project root:
```bash
# Alpaca (Paper Trading)
ALPACA_API_KEY=your_paper_key
ALPACA_SECRET_KEY=your_paper_secret
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# Finnhub
FINNHUB_API_KEY=your_finnhub_key

# Alpha Vantage
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_key
```

### 4. Run Phase 1 (Data Pipeline)
```bash
# Test Alpaca connection
python test_alpaca_connection.py

# Fetch historical data (2020–2024)
python fetch_historical_data.py

# Build fundamental universe
python fetch_fundamentals.py

# Generate summary report
python generate_universe_report.py
```

---

## Project Structure

```
trading-bot/
├── .claude/                      # Claude Code configuration
│   ├── CLAUDE.md                 # Master project brief
│   └── skills/                   # API integration docs
│       ├── alpaca-api.md
│       ├── finnhub-api.md
│       └── alpha-vantage-api.md
├── data/                         # Data fetching scripts
│   ├── fetch_historical.py       # OHLCV price data
│   ├── fetch_fundamentals.py     # Fundamental screener
│   └── fetch_sentiment.py        # Sentiment analysis
├── strategy/                     # Trading logic
│   ├── indicators.py             # RSI, MACD, Bollinger, EMA
│   ├── signals.py                # Entry/exit conditions
│   └── position_sizing.py        # ATR-based sizing
├── risk/                         # Risk management
│   ├── stop_loss.py              # Trailing stop logic
│   ├── kill_switch.py            # Emergency shutdown
│   └── sector_limits.py          # Diversification enforcement
├── backtesting/                  # Strategy validation
│   ├── backtest_engine.py        # Backtrader runner
│   └── performance_metrics.py    # Sharpe, drawdown, etc.
├── live/                         # Production deployment
│   ├── bot.py                    # Main event loop
│   ├── monitor.py                # Dashboard/logging
│   └── alerts.py                 # Email/SMS notifications
├── .env                          # API keys (gitignored)
├── .gitignore
├── requirements.txt
├── PHASE_1_PLAN.md               # Current phase prompts
└── README.md
```

---

## Development Phases

### ✅ Phase 1: Data Pipeline (Week 1)
- [x] Alpaca API connection
- [x] Historical OHLCV data (2020–2024)
- [x] Fundamental universe screener
- [x] Data validation

### ✅ Phase 2: Backtesting (Week 2–3)
- [x] Implement technical indicators
- [x] Code entry/exit logic
- [x] Run backtest on 3+ years
- [x] Validate Sharpe ratio 1.0–1.8

### ⏳ Phase 3: Paper Trading (Week 4–7)
- [ ] Deploy to Alpaca paper account
- [ ] Real-time signal generation
- [ ] Live order execution
- [ ] Monitor for 2–4 weeks

### ⏳ Phase 4: Live Deployment (Week 8+)
- [ ] Migrate to live account
- [ ] Enable kill switches
- [ ] Implement alerts
- [ ] Weekly performance review

---

## Core Strategy

### Entry Conditions (ALL required)
1. **Fundamental pass** — Market cap >$2B, ROE >15%, P/B <2.0, earnings growth >0%
2. **Trend filter** — Price > 200-period EMA
3. **Oversold** — RSI(14) < 35
4. **Momentum** — MACD crosses above signal line
5. **Volatility** — Price < Lower Bollinger Band × 1.01
6. **Sentiment** — 7-day rolling average > 0

### Exit Conditions (ANY triggers)
- Price drops below ATR trailing stop (2.5× ATR)
- RSI(14) > 65 (overbought)
- Hold time > 21 trading days

### Risk Management
- **Position sizing**: 1.5% risk per trade (ATR-based)
- **Max single position**: 15% of portfolio
- **Max sector exposure**: 25% of portfolio
- **Session kill switch**: -5% daily loss → halt system
- **Drawdown pause**: -15% from peak → pause 48–72 hours

---

## Safety Mechanisms

### Pre-Flight Checklist (Before Live Trading)
- [ ] Backtesting Sharpe ≥ 1.0
- [ ] Paper trading 2+ weeks without errors
- [ ] Kill switch tested (manual + automatic)
- [ ] API keys in `.env` (never hardcoded)
- [ ] Position size limits functional
- [ ] Sector diversification enforced

### Emergency Shutdown
If session loss exceeds -5%:
1. Cancel all pending orders
2. Close all positions
3. Halt bot execution
4. Send email alert
5. Wait for manual review

---

## API Rate Limits

| API | Free Tier | Usage |
|-----|-----------|-------|
| Alpaca | 200/min | Data + orders |
| Finnhub | 60/min | Sentiment |
| Alpha Vantage | 25/day | Fundamentals (consider upgrade) |

**Caching Strategy**: Store fundamental data locally (SQLite) to reduce API calls

---

## Monitoring

### Daily Metrics
- Portfolio value
- P&L ($, %)
- Open positions
- Distance to kill switch

### Weekly Review
- Win rate
- Avg winner/loser ratio
- Sharpe ratio (30-day rolling)
- Sector exposure

---

## Troubleshooting

### Issue: "Insufficient Buying Power"
**Cause**: Trying to allocate more than available cash  
**Fix**: Check `account.buying_power` before submitting orders

### Issue: "Market is closed"
**Cause**: Attempting to trade outside 9:30 AM – 4:00 PM ET  
**Fix**: Check `trading_client.get_clock().is_open` before orders

### Issue: Alpha Vantage rate limit
**Cause**: Exceeded 25 API calls/day  
**Fix**: Upgrade to paid plan or spread screening over multiple days

---

## Resources

### Documentation
- **Alpaca API**: https://docs.alpaca.markets/
- **Finnhub API**: https://finnhub.io/docs/api
- **Alpha Vantage API**: https://www.alphavantage.co/documentation/

### Trading Concepts
- **Backtrader**: https://www.backtrader.com/docu/
- **Technical Analysis**: https://www.investopedia.com/technical-analysis-4689657
- **Risk Management**: https://www.investopedia.com/terms/r/riskmanagement.asp

---

## Disclaimer

⚠️ **Trading involves substantial risk of loss**

- Past performance ≠ future results
- Backtesting can overfit historical data
- API failures and market anomalies can occur
- Never invest more than you can afford to lose
- This bot is for educational purposes

**Use paper trading extensively before risking real capital**

---

## License

MIT License — See LICENSE file for details

---

## Support

Issues or questions? Check:
1. `.claude/CLAUDE.md` — Full project context
2. `.claude/skills/` — API integration guides
3. `PHASE_X_PLAN.md` — Current development phase

For bugs: Open GitHub issue with error logs and reproduction steps
