# Phase 1: Data Pipeline + Fundamental Universe

**Duration**: Week 1  
**Objective**: Establish data infrastructure — fetch historical prices, screen fundamental universe, validate data quality

---

## Prerequisites

### 1. Create API Accounts
- **Alpaca** (https://alpaca.markets) — Generate paper trading API keys
- **Finnhub** (https://finnhub.io/register) — Generate API key (free tier)
- **Alpha Vantage** (https://www.alphavantage.co/support/#api-key) — Generate API key (free tier)

### 2. Set Up `.env` File
Create `.env` in project root:

```bash
# Alpaca (Paper Trading)
ALPACA_API_KEY=your_paper_key_here
ALPACA_SECRET_KEY=your_paper_secret_here
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# Finnhub
FINNHUB_API_KEY=your_finnhub_key

# Alpha Vantage
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_key
```

**Add to `.gitignore`**:
```
.env
```

### 3. Install Dependencies
```bash
pip install alpaca-py finnhub-python alpha-vantage requests pandas numpy python-dotenv sqlite3
```

---

## Milestone 1: Alpaca Connection & Historical Data

### Prompt 1.1: Test Alpaca Connection

**Paste this into Claude Code terminal:**

```
CONTEXT: Setting up automated trading bot infrastructure — Phase 1 of 4-phase build plan

TASK: Create a Python script that tests the Alpaca API connection and retrieves account information

REQUIREMENTS:
- Load API keys from .env file (never hardcode)
- Use alpaca-py SDK
- Test both TradingClient (for orders/positions) and StockHistoricalDataClient (for price data)
- Print account details: portfolio value, buying power, cash, equity
- Handle errors gracefully (invalid keys, network issues)

OUTPUT:
File: test_alpaca_connection.py

Expected output when run:
✓ Alpaca API connection successful
Portfolio Value: $100,000.00
Buying Power: $100,000.00
Cash: $100,000.00
Equity: $0.00

VALIDATION:
Run the script and confirm it prints account details without errors
```

---

### Prompt 1.2: Fetch Historical OHLCV Data (2020–2024)

**Paste this into Claude Code terminal:**

```
CONTEXT: Building data pipeline for backtesting — need 3+ years of daily price data

TASK: Create a Python script that fetches historical OHLCV (Open, High, Low, Close, Volume) data from Alpaca for backtesting

REQUIREMENTS:
- Fetch daily bars from January 1, 2020 to December 31, 2024
- Start with test tickers: AAPL, MSFT, GOOGL, TSLA, NVDA
- Save data to SQLite database (table: price_history)
- Database schema:
  - symbol TEXT
  - date DATE
  - open REAL
  - high REAL
  - low REAL
  - close REAL
  - volume INTEGER
  - PRIMARY KEY (symbol, date)
- Include progress indicator (e.g., "Fetching AAPL... 1/5")
- Handle API errors (symbol not found, rate limits)

OUTPUT:
Files:
1. fetch_historical_data.py
2. trading_bot.db (SQLite database)

Expected database content:
~1,250 rows per ticker (5 years × 250 trading days)

VALIDATION:
1. Run the script
2. Confirm database created with ~6,250 rows (5 tickers × 1,250 days)
3. Query database: SELECT * FROM price_history WHERE symbol='AAPL' LIMIT 5;
```

---

### Prompt 1.3: Add Volume Filter to Historical Data

**Paste this into Claude Code terminal:**

```
CONTEXT: Liquidity is critical for small accounts — need to filter out low-volume stocks

TASK: Modify the historical data fetcher to calculate average daily volume and exclude stocks below 1M shares/day

REQUIREMENTS:
- After fetching data, calculate average daily volume per ticker
- If avg volume < 1,000,000 shares, remove ticker from database and log reason
- Print summary: "5 tickers fetched, 1 excluded (TSLA: avg volume 850K)"
- Update database to only include liquid stocks

OUTPUT:
Modified: fetch_historical_data.py

Expected behavior:
If a ticker has low volume, script prints:
"✗ TSLA excluded (avg volume: 850,234 shares, minimum: 1,000,000)"

VALIDATION:
Run script with mix of high/low volume tickers
Confirm only stocks with avg volume > 1M are in database
```

---

## Milestone 2: Fundamental Universe Screener

### Prompt 2.1: Fetch Fundamental Data (Alpha Vantage)

**Paste this into Claude Code terminal:**

```
CONTEXT: Building fundamental screener to filter tradable universe

TASK: Create a Python script that fetches fundamental metrics from Alpha Vantage and applies quality filters

REQUIREMENTS:
- Input: List of candidate tickers (start with S&P 100 top 25 by market cap)
- Fetch from Alpha Vantage OVERVIEW endpoint:
  - Market Capitalization
  - ReturnOnEquityTTM
  - PriceToBookRatio
  - Sector
- Apply fundamental filters:
  - Market Cap > $2 billion
  - ROE > 15%
  - P/B Ratio < 2.0
  - P/B Ratio > 0 (valid data)
- Save qualified tickers to SQLite (table: fundamental_universe)
- Database schema:
  - symbol TEXT PRIMARY KEY
  - market_cap REAL
  - roe REAL
  - pb_ratio REAL
  - sector TEXT
  - last_updated DATE
- Respect Alpha Vantage rate limit: 5 calls/minute (12-second delay between requests)
- Track daily quota: Stop after 25 calls (free tier limit)

OUTPUT:
Files:
1. fetch_fundamentals.py
2. sp100_top25.csv (input file with candidate tickers)
3. Updated trading_bot.db with fundamental_universe table

Expected output:
"Screened 25 tickers: 12 qualified, 13 excluded"

VALIDATION:
1. Run script (will take ~5 minutes due to rate limits)
2. Confirm fundamental_universe table has 10–15 qualified stocks
3. Manually verify one ticker (e.g., AAPL) meets all criteria
```

---

### Prompt 2.2: Add Earnings Growth Filter

**Paste this into Claude Code terminal:**

```
CONTEXT: Fundamental screener needs earnings growth validation (YoY > 0%)

TASK: Enhance fundamental screener to check year-over-year earnings growth using Alpha Vantage INCOME_STATEMENT endpoint

REQUIREMENTS:
- For each ticker that passed initial filters (market cap, ROE, P/B), fetch income statement
- Compare most recent annual net income vs prior year
- Calculate YoY growth percentage: ((current - prior) / prior) * 100
- Exclude if earnings growth ≤ 0%
- Add earnings_growth column to fundamental_universe table
- Handle missing data (some companies may not have 2 years of data)

OUTPUT:
Modified: fetch_fundamentals.py

Expected behavior:
If AAPL has $95B net income (current) vs $85B (prior):
Growth = ((95 - 85) / 85) * 100 = +11.8%
Result: AAPL qualified ✓

VALIDATION:
Rerun script on previously qualified tickers
Confirm earnings_growth column populated
Verify some stocks excluded due to negative growth
```

---

## Milestone 3: Data Validation & Export

### Prompt 3.1: Generate Universe Summary Report

**Paste this into Claude Code terminal:**

```
CONTEXT: Need to validate fundamental screener output before proceeding to Phase 2

TASK: Create a script that generates a summary report of the qualified stock universe

REQUIREMENTS:
- Query fundamental_universe table
- Calculate statistics:
  - Total qualified stocks
  - Average market cap
  - Average ROE
  - Average P/B ratio
  - Sector breakdown (count per sector)
- Export to CSV: qualified_universe.csv
- Columns: symbol, market_cap, roe, pb_ratio, earnings_growth, sector
- Sort by market cap descending

OUTPUT:
Files:
1. generate_universe_report.py
2. qualified_universe.csv

Expected CSV format:
symbol,market_cap,roe,pb_ratio,earnings_growth,sector
AAPL,2800000000000,18.5,1.2,11.8,Technology
MSFT,2500000000000,20.3,1.5,15.2,Technology
...

Console output:
=== Fundamental Universe Summary ===
Total Qualified Stocks: 12
Average Market Cap: $450B
Average ROE: 18.2%
Average P/B: 1.45
Sector Breakdown:
  Technology: 5
  Healthcare: 3
  Consumer Discretionary: 2
  Financials: 2

VALIDATION:
1. Run script
2. Open CSV in Excel/Google Sheets
3. Manually verify 3 random stocks meet all criteria
4. Confirm no single sector has >3 stocks (diversification check)
```

---

### Prompt 3.2: Validate Historical Data Completeness

**Paste this into Claude Code terminal:**

```
CONTEXT: Backtesting requires complete, gap-free historical data

TASK: Create a validation script that checks for missing data in price_history table

REQUIREMENTS:
- For each symbol in fundamental_universe:
  - Count total trading days in database (should be ~1,250 for 2020–2024)
  - Identify gaps (missing dates between first and last record)
  - Check for zero/negative prices (data quality issue)
  - Check for zero volume (suspicious)
- Print report:
  - Symbols with complete data ✓
  - Symbols with gaps (list missing date ranges)
  - Symbols with quality issues
- Export issues to data_quality_report.txt

OUTPUT:
Files:
1. validate_historical_data.py
2. data_quality_report.txt

Expected output:
=== Historical Data Validation ===
AAPL: ✓ Complete (1,258 days, no gaps)
MSFT: ✓ Complete (1,258 days, no gaps)
GOOGL: ⚠ Gap detected (2022-07-15 to 2022-07-18)
TSLA: ✗ Insufficient data (only 892 days)

VALIDATION:
Run script on all qualified universe tickers
Investigate any gaps (may be legitimate holidays/suspensions)
Remove tickers with significant data issues from universe
```

---

## Phase 1 Checkpoint

### Success Criteria (ALL must pass)

- [ ] **Alpaca connection working** — test_alpaca_connection.py runs without errors
- [ ] **Historical data fetched** — price_history table has ~1,250 rows per ticker
- [ ] **Volume filter applied** — All stocks have avg daily volume > 1M shares
- [ ] **Fundamental universe built** — 10–15 qualified stocks in fundamental_universe table
- [ ] **All filters validated**:
  - [ ] Market cap > $2B
  - [ ] ROE > 15%
  - [ ] P/B < 2.0
  - [ ] Earnings growth > 0%
- [ ] **Data quality confirmed** — No significant gaps or corrupted data
- [ ] **Export successful** — qualified_universe.csv ready for Phase 2

### Validation Meeting

**Before proceeding to Phase 2, share with me:**

1. Screenshot of qualified_universe.csv (first 10 rows)
2. Output of data_quality_report.txt
3. Count of qualified stocks per sector

**I will verify:**
- No overfitting to single sector (Technology often dominates)
- No penny stocks or micro-caps slipped through
- Data completeness sufficient for backtesting

---

## Troubleshooting

### Issue: Alpha Vantage Rate Limit Hit Early

**Symptom**: Script stops after 10–15 tickers instead of 25

**Solution**: Check if you're making duplicate API calls (OVERVIEW + INCOME_STATEMENT = 2 calls per ticker)

**Fix**: Batch process — fetch OVERVIEW for all 25, then INCOME_STATEMENT only for those that passed initial filters

---

### Issue: Some Tickers Missing Fundamental Data

**Symptom**: Alpha Vantage returns empty response for certain symbols

**Solution**: These may be ETFs, foreign stocks, or recently delisted companies

**Fix**: Maintain a manual exclusion list in sp100_top25.csv (e.g., remove BRK.B which has unusual structure)

---

### Issue: Historical Data Has Gaps

**Symptom**: validate_historical_data.py reports missing dates

**Solution**: Check if gaps align with market holidays (NYSE closed) or trading halts

**Fix**: If gaps are holidays, ignore. If gaps are random, refetch that ticker's data.

---

## Next Steps After Phase 1

Once checkpoint passed, I will provide:

1. **Phase 2 prompts** — Backtesting engine implementation
2. **Indicator validation tests** — Ensure RSI, MACD, Bollinger Bands calculated correctly
3. **Strategy parameter optimization** — Fine-tune entry/exit thresholds

**Estimated time to Phase 2**: 1 week (if running screener daily due to Alpha Vantage limits)

---

## Files Created in Phase 1

```
trading-bot/
├── .env (gitignored)
├── .gitignore
├── trading_bot.db (SQLite database)
├── test_alpaca_connection.py
├── fetch_historical_data.py
├── fetch_fundamentals.py
├── generate_universe_report.py
├── validate_historical_data.py
├── sp100_top25.csv (input)
├── qualified_universe.csv (output)
└── data_quality_report.txt (output)
```

---

## API Usage Tracker (Phase 1)

| API | Free Tier Limit | Phase 1 Usage | Risk of Exceeding |
|-----|-----------------|---------------|-------------------|
| Alpaca | 200/min | ~10 calls | Low |
| Alpha Vantage | 25/day | 25/day × 7 days = 175 | **HIGH** (spread over week) |
| Finnhub | 60/min | 0 (not used in Phase 1) | None |

**Recommendation**: If screening full S&P 500, upgrade Alpha Vantage to $50/month plan (75 calls/day) or use Financial Modeling Prep (250 free calls/day)
