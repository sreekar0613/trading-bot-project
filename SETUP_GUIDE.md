# Setup Guide — Automated Trading Bot

Complete setup instructions from zero to Phase 1 ready.

---

## Part 1: Create API Accounts

### 1. Alpaca (Paper Trading)

**Purpose**: Broker for order execution + historical market data

1. Go to https://alpaca.markets
2. Click "Sign Up" → Select "Individual" account
3. Complete identity verification (requires SSN, address)
4. Once approved, navigate to **Paper Trading** section
5. Generate API keys:
   - Dashboard → API Keys (Paper) → "Generate New Key"
   - Save **API Key** and **Secret Key** (shown only once)

**Cost**: Free (paper trading has unlimited fake money)

---

### 2. Finnhub (Sentiment Analysis)

**Purpose**: News sentiment scores for trading signals

1. Go to https://finnhub.io/register
2. Sign up with email (no identity verification required)
3. Verify email
4. Dashboard → API Keys → Copy your key

**Cost**: Free tier (60 calls/minute)

---

### 3. Alpha Vantage (Fundamental Data)

**Purpose**: Market cap, ROE, P/E ratios for universe screening

1. Go to https://www.alphavantage.co/support/#api-key
2. Enter email → Click "GET FREE API KEY"
3. Copy API key from confirmation page

**Cost**: Free tier (25 calls/day — **will need upgrade or alternative for full S&P screening**)

**⚠️ Limitation**: Free tier insufficient for screening 500+ stocks. Options:
- **Upgrade**: $50/month for 75 calls/day
- **Alternative**: Financial Modeling Prep (https://financialmodelingprep.com/) — 250 free calls/day

---

## Part 2: Local Environment Setup

### 1. Install Python 3.11+

**Check current version**:
```bash
python --version
```

If < 3.11, download from https://www.python.org/downloads/

---

### 2. Clone Project Files

If you received project as ZIP:
```bash
unzip trading-bot-project.zip
cd trading-bot-project
```

If in GitHub repo:
```bash
git clone <repo-url>
cd trading-bot
```

---

### 3. Create Virtual Environment

**macOS/Linux**:
```bash
python -m venv venv
source venv/bin/activate
```

**Windows**:
```bash
python -m venv venv
venv\Scripts\activate
```

You should see `(venv)` prefix in terminal.

---

### 4. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**⚠️ Note on TA-Lib**:  
`ta-lib` requires C dependencies. If installation fails:

**macOS**:
```bash
brew install ta-lib
pip install ta-lib
```

**Linux (Ubuntu/Debian)**:
```bash
sudo apt-get install build-essential
wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
tar -xzf ta-lib-0.4.0-src.tar.gz
cd ta-lib/
./configure --prefix=/usr
make
sudo make install
pip install ta-lib
```

**Windows**:  
Download precompiled wheel from https://www.lfd.uci.edu/~gohlke/pythonlibs/#ta-lib

**Fallback**: Use `pandas-ta` instead (pure Python, no compilation needed):
```bash
pip install pandas-ta
```

---

### 5. Create `.env` File

In project root, create file named `.env`:

```bash
# Alpaca Paper Trading Keys
ALPACA_API_KEY=PK...your_paper_key_here
ALPACA_SECRET_KEY=...your_paper_secret_here
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# Finnhub
FINNHUB_API_KEY=...your_finnhub_key

# Alpha Vantage
ALPHA_VANTAGE_API_KEY=...your_alpha_vantage_key
```

**Security Check**:
```bash
# Verify .env is gitignored (should show up in this list)
cat .gitignore | grep .env
```

---

### 6. Install Git Hooks (Optional but Recommended)

Prevents accidentally committing API keys:

```bash
# Copy pre-commit hook
cp .git-hooks/pre-commit .git/hooks/pre-commit

# Make executable
chmod +x .git/hooks/pre-commit
```

**Test it**:
```bash
# Create test file with fake API key
echo "ALPACA_API_KEY = 'test123'" > test_api.py

# Try to commit (should block)
git add test_api.py
git commit -m "test"

# Expected output: "ERROR: API key detected in staged files"

# Clean up
rm test_api.py
```

---

## Part 3: Verify Setup

### 1. Test Alpaca Connection

Create `test_setup.py`:

```python
from alpaca.trading.client import TradingClient
import os
from dotenv import load_dotenv

load_dotenv()

try:
    client = TradingClient(
        api_key=os.getenv('ALPACA_API_KEY'),
        secret_key=os.getenv('ALPACA_SECRET_KEY'),
        paper=True
    )
    
    account = client.get_account()
    
    print("✓ Alpaca connection successful")
    print(f"Portfolio Value: ${account.portfolio_value}")
    print(f"Buying Power: ${account.buying_power}")
    
except Exception as e:
    print(f"✗ Alpaca connection failed: {e}")
```

Run:
```bash
python test_setup.py
```

**Expected output**:
```
✓ Alpaca connection successful
Portfolio Value: $100000.00
Buying Power: $100000.00
```

---

### 2. Test Finnhub API

Add to `test_setup.py`:

```python
import finnhub

finnhub_client = finnhub.Client(api_key=os.getenv('FINNHUB_API_KEY'))

try:
    sentiment = finnhub_client.news_sentiment('AAPL')
    print(f"✓ Finnhub connection successful")
    print(f"AAPL Sentiment Score: {sentiment['companyNewsScore']:.3f}")
except Exception as e:
    print(f"✗ Finnhub connection failed: {e}")
```

**Expected output**:
```
✓ Finnhub connection successful
AAPL Sentiment Score: 0.654
```

---

### 3. Test Alpha Vantage API

Add to `test_setup.py`:

```python
import requests

url = "https://www.alphavantage.co/query"
params = {
    'function': 'OVERVIEW',
    'symbol': 'AAPL',
    'apikey': os.getenv('ALPHA_VANTAGE_API_KEY')
}

try:
    response = requests.get(url, params=params)
    data = response.json()
    
    if 'Symbol' in data:
        print("✓ Alpha Vantage connection successful")
        print(f"AAPL Market Cap: ${float(data['MarketCapitalization']):,.0f}")
    else:
        print(f"✗ Alpha Vantage error: {data.get('Note', 'Unknown error')}")
except Exception as e:
    print(f"✗ Alpha Vantage connection failed: {e}")
```

**Expected output**:
```
✓ Alpha Vantage connection successful
AAPL Market Cap: $2,800,000,000,000
```

---

## Part 4: Initialize Database

Create `init_database.py`:

```python
import sqlite3

conn = sqlite3.connect('trading_bot.db')
cursor = conn.cursor()

# Create price_history table
cursor.execute('''
CREATE TABLE IF NOT EXISTS price_history (
    symbol TEXT NOT NULL,
    date DATE NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume INTEGER,
    PRIMARY KEY (symbol, date)
)
''')

# Create fundamental_universe table
cursor.execute('''
CREATE TABLE IF NOT EXISTS fundamental_universe (
    symbol TEXT PRIMARY KEY,
    market_cap REAL,
    roe REAL,
    pb_ratio REAL,
    sector TEXT,
    earnings_growth REAL,
    last_updated DATE
)
''')

# Create sentiment_cache table
cursor.execute('''
CREATE TABLE IF NOT EXISTS sentiment_cache (
    symbol TEXT NOT NULL,
    date DATE NOT NULL,
    sentiment_score REAL,
    buzz_ratio REAL,
    articles_count INTEGER,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, date)
)
''')

conn.commit()
conn.close()

print("✓ Database initialized: trading_bot.db")
print("  - price_history table created")
print("  - fundamental_universe table created")
print("  - sentiment_cache table created")
```

Run:
```bash
python init_database.py
```

Verify:
```bash
sqlite3 trading_bot.db ".tables"
# Expected: fundamental_universe  price_history  sentiment_cache
```

---

## Part 5: Pre-Flight Checklist

Before starting Phase 1 prompts, verify:

- [ ] **Python 3.11+** installed
- [ ] **Virtual environment** activated (see `(venv)` in terminal)
- [ ] **All dependencies** installed (`pip list` shows alpaca-py, finnhub-python, etc.)
- [ ] **API keys** in `.env` file (not hardcoded)
- [ ] **Alpaca connection** working (test_setup.py succeeded)
- [ ] **Finnhub connection** working
- [ ] **Alpha Vantage connection** working
- [ ] **Database initialized** (trading_bot.db exists with 3 tables)
- [ ] **Git hooks installed** (prevents API key commits)
- [ ] **.gitignore present** (.env file excluded from git)

---

## Part 6: Start Phase 1

You're now ready to begin data pipeline development.

**Next steps**:

1. Open `PHASE_1_PLAN.md`
2. Copy **Prompt 1.1** into Claude Code terminal
3. Run generated script
4. Share output with validation partner
5. Proceed to next prompt

**Estimated Phase 1 duration**: 1 week (due to Alpha Vantage rate limits)

---

## Troubleshooting

### Issue: `alpaca-py` import fails

**Solution**: Ensure virtual environment is activated
```bash
which python  # Should show path to venv/bin/python
```

---

### Issue: "No module named dotenv"

**Solution**:
```bash
pip install python-dotenv
```

---

### Issue: Alpaca returns "Invalid API credentials"

**Solution**: Verify you're using **Paper Trading** keys, not Live Trading keys
- Keys should start with `PK...` (paper) not `AK...` (live)

---

### Issue: Alpha Vantage returns "Thank you for using Alpha Vantage!"

**Cause**: Rate limit exceeded (25 calls/day)

**Solutions**:
1. Wait 24 hours for quota reset
2. Upgrade to paid plan
3. Use cached data (if available)

---

### Issue: SQLite database locked

**Cause**: Database file open in another program (e.g., DB Browser)

**Solution**: Close all programs accessing `trading_bot.db`

---

## Support Resources

- **Alpaca Docs**: https://docs.alpaca.markets/
- **Finnhub Docs**: https://finnhub.io/docs/api
- **Alpha Vantage Docs**: https://www.alphavantage.co/documentation/
- **Python Dotenv**: https://pypi.org/project/python-dotenv/
- **SQLite Tutorial**: https://www.sqlitetutorial.net/

---

## Security Reminders

🔒 **NEVER**:
- Commit `.env` file to git
- Share API keys in screenshots/messages
- Hardcode API keys in Python files
- Push `trading_bot.db` to public repos (may contain cached data)

✅ **ALWAYS**:
- Use `os.getenv()` to load API keys
- Keep `.env` in `.gitignore`
- Regenerate keys if accidentally exposed
- Use paper trading keys during development

---

Ready? → Open `PHASE_1_PLAN.md` and start with Prompt 1.1
