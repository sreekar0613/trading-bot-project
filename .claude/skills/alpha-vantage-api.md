# Alpha Vantage API Integration — Skill Documentation

## Overview
Alpha Vantage provides fundamental financial data (market cap, ROE, P/E ratios) and sentiment analysis. Use for universe screening (fundamental filters) and as backup sentiment source.

**Official Docs**: https://www.alphavantage.co/documentation/

---

## Authentication

### API Key
- **Free Tier**: 25 API calls/day (very restrictive)
- **Paid Tier**: 75–1,200 calls/day depending on plan

**Sign Up**: https://www.alphavantage.co/support/#api-key

### Installation
```bash
pip install alpha-vantage requests
```

### Initialization
```python
from alpha_vantage.fundamentaldata import FundamentalData
import os

fd = FundamentalData(key=os.getenv('ALPHA_VANTAGE_API_KEY'), output_format='json')
```

**Security**: Store key in `.env` file

---

## Key Endpoints

### 1. Company Overview (Fundamental Screening)
**Purpose**: Get market cap, ROE, P/E, P/B for fundamental filters

**Function**: `OVERVIEW`

```python
import requests

def get_company_fundamentals(symbol):
    """Fetch fundamental metrics for a single company"""
    
    url = "https://www.alphavantage.co/query"
    params = {
        'function': 'OVERVIEW',
        'symbol': symbol,
        'apikey': os.getenv('ALPHA_VANTAGE_API_KEY')
    }
    
    response = requests.get(url, params=params)
    data = response.json()
    
    # Extract key metrics
    fundamentals = {
        'symbol': data.get('Symbol'),
        'market_cap': float(data.get('MarketCapitalization', 0)),
        'roe': float(data.get('ReturnOnEquityTTM', 0)) * 100,  # Convert to percentage
        'pb_ratio': float(data.get('PriceToBookRatio', 0)),
        'pe_ratio': float(data.get('PERatio', 0)),
        'sector': data.get('Sector'),
        'industry': data.get('Industry')
    }
    
    return fundamentals

# Example usage
aapl_fundamentals = get_company_fundamentals('AAPL')
print(f"AAPL Market Cap: ${aapl_fundamentals['market_cap']:,.0f}")
print(f"AAPL ROE: {aapl_fundamentals['roe']:.2f}%")
print(f"AAPL P/B: {aapl_fundamentals['pb_ratio']:.2f}")
```

**Response Fields** (relevant for strategy):
- `MarketCapitalization` — Total market value (require > $2B)
- `ReturnOnEquityTTM` — ROE (require > 15%)
- `PriceToBookRatio` — P/B ratio (require < 2.0)
- `Sector` — GICS sector (for 25% diversification limit)
- `52WeekHigh` / `52WeekLow` — Useful for volatility checks

---

### 2. Income Statement (Earnings Growth)
**Purpose**: Verify year-over-year earnings growth > 0%

**Function**: `INCOME_STATEMENT`

```python
def get_earnings_growth(symbol):
    """Check if earnings are growing YoY"""
    
    url = "https://www.alphavantage.co/query"
    params = {
        'function': 'INCOME_STATEMENT',
        'symbol': symbol,
        'apikey': os.getenv('ALPHA_VANTAGE_API_KEY')
    }
    
    response = requests.get(url, params=params)
    data = response.json()
    
    if 'annualReports' not in data or len(data['annualReports']) < 2:
        return None
    
    # Get last two years of net income
    current_year = float(data['annualReports'][0]['netIncome'])
    prior_year = float(data['annualReports'][1]['netIncome'])
    
    growth_pct = ((current_year - prior_year) / prior_year) * 100
    
    return growth_pct

# Example
growth = get_earnings_growth('AAPL')
if growth and growth > 0:
    print(f"AAPL earnings growth: +{growth:.1f}% YoY ✓")
else:
    print(f"AAPL earnings growth: {growth:.1f}% YoY ✗")
```

---

### 3. News Sentiment (Backup to Finnhub)
**Purpose**: Alternative sentiment source if Finnhub rate limits are restrictive

**Function**: `NEWS_SENTIMENT`

```python
def get_alpha_vantage_sentiment(symbol):
    """Fetch sentiment analysis from Alpha Vantage"""
    
    url = "https://www.alphavantage.co/query"
    params = {
        'function': 'NEWS_SENTIMENT',
        'tickers': symbol,
        'limit': 50,  # Last 50 articles
        'apikey': os.getenv('ALPHA_VANTAGE_API_KEY')
    }
    
    response = requests.get(url, params=params)
    data = response.json()
    
    if 'feed' not in data:
        return None
    
    # Calculate average sentiment
    sentiment_scores = []
    
    for article in data['feed']:
        # Alpha Vantage provides per-ticker sentiment
        for ticker_sentiment in article['ticker_sentiment']:
            if ticker_sentiment['ticker'] == symbol:
                score = float(ticker_sentiment['ticker_sentiment_score'])
                sentiment_scores.append(score)
    
    if len(sentiment_scores) == 0:
        return None
    
    avg_sentiment = sum(sentiment_scores) / len(sentiment_scores)
    return avg_sentiment

# Example
sentiment = get_alpha_vantage_sentiment('AAPL')
print(f"AAPL sentiment: {sentiment:.3f}")
```

**Sentiment Score Scale**:
- `-1.0` to `-0.35` — Bearish
- `-0.35` to `0.35` — Neutral
- `0.35` to `1.0` — Bullish

**Strategy Rule**: Only enter if sentiment > 0 (neutral to bullish)

---

## Fundamental Universe Screener

### Build Stock Universe (Weekly Refresh)
```python
import pandas as pd
import time

def build_fundamental_universe(candidate_tickers):
    """
    Filter stock universe by fundamental criteria.
    
    Filters:
    - Market Cap > $2B
    - ROE > 15%
    - P/B < 2.0
    - Earnings Growth > 0%
    """
    
    qualified_stocks = []
    
    for symbol in candidate_tickers:
        try:
            # Fetch fundamentals
            fundamentals = get_company_fundamentals(symbol)
            
            # Apply filters
            if (fundamentals['market_cap'] > 2_000_000_000 and  # > $2B
                fundamentals['roe'] > 15.0 and                  # > 15% ROE
                fundamentals['pb_ratio'] < 2.0 and              # < 2.0 P/B
                fundamentals['pb_ratio'] > 0):                  # Valid P/B
                
                # Check earnings growth
                growth = get_earnings_growth(symbol)
                
                if growth and growth > 0:
                    qualified_stocks.append({
                        'symbol': symbol,
                        'market_cap': fundamentals['market_cap'],
                        'roe': fundamentals['roe'],
                        'pb_ratio': fundamentals['pb_ratio'],
                        'sector': fundamentals['sector'],
                        'earnings_growth': growth
                    })
                    
                    print(f"✓ {symbol} qualified")
                else:
                    print(f"✗ {symbol} failed (negative earnings growth)")
            else:
                print(f"✗ {symbol} failed fundamental filters")
        
        except Exception as e:
            print(f"ERROR: {symbol} — {e}")
        
        # Rate limit: 25 calls/day on free tier = max 25 tickers
        time.sleep(12)  # 5 calls/minute to stay safe
    
    # Convert to DataFrame
    df = pd.DataFrame(qualified_stocks)
    df.to_csv('qualified_universe.csv', index=False)
    
    print(f"\n{len(qualified_stocks)} stocks passed fundamental screening")
    return df

# Example: Screen S&P 500 tickers (will take ~2 hours on free tier)
# sp500_tickers = ['AAPL', 'MSFT', 'GOOGL', ...]  # Load from file
# universe = build_fundamental_universe(sp500_tickers[:25])  # Free tier limit
```

**CRITICAL ISSUE**: Free tier (25 calls/day) is insufficient for screening hundreds of stocks.

**Solutions**:
1. **Upgrade to paid tier** ($50/month for 75 calls/day, $250/month for 600 calls/day)
2. **Use pre-filtered universe** — Start with S&P 500 or Russell 1000, screen 25 stocks/day over several weeks
3. **Alternative data source** — Financial Modeling Prep (https://financialmodelingprep.com/) has higher free tier limits

---

## Rate Limit Management

### Free Tier (25 Calls/Day)
```python
import sqlite3
from datetime import datetime, date

def check_daily_quota():
    """Track API calls to avoid exceeding 25/day limit"""
    
    conn = sqlite3.connect('api_usage.db')
    cursor = conn.cursor()
    
    # Create table if not exists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS api_calls (
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Count today's calls
    today = date.today().isoformat()
    cursor.execute('''
        SELECT COUNT(*) FROM api_calls
        WHERE DATE(timestamp) = ?
    ''', (today,))
    
    calls_today = cursor.fetchone()[0]
    
    if calls_today >= 25:
        print(f"ERROR: Daily quota exceeded ({calls_today}/25)")
        conn.close()
        return False
    
    # Log this call
    cursor.execute('INSERT INTO api_calls DEFAULT VALUES')
    conn.commit()
    conn.close()
    
    print(f"API calls today: {calls_today + 1}/25")
    return True

# Use before every API request
if check_daily_quota():
    fundamentals = get_company_fundamentals('AAPL')
```

---

## Data Caching Strategy

### SQLite Cache Schema
```sql
CREATE TABLE fundamental_data (
    symbol TEXT PRIMARY KEY,
    market_cap REAL,
    roe REAL,
    pb_ratio REAL,
    pe_ratio REAL,
    sector TEXT,
    earnings_growth REAL,
    last_updated DATE
);

-- Example insert
INSERT OR REPLACE INTO fundamental_data
VALUES ('AAPL', 2800000000000, 18.5, 1.2, 28.3, 'Technology', 12.4, '2024-04-22');
```

**Refresh Logic**:
```python
def get_cached_fundamentals(symbol, max_age_days=7):
    """Get fundamentals from cache, refresh if stale"""
    
    conn = sqlite3.connect('fundamental_cache.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM fundamental_data
        WHERE symbol = ? AND last_updated >= DATE('now', '-{} days')
    '''.format(max_age_days), (symbol,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        print(f"Using cached data for {symbol}")
        return {
            'symbol': row[0],
            'market_cap': row[1],
            'roe': row[2],
            'pb_ratio': row[3],
            'pe_ratio': row[4],
            'sector': row[5],
            'earnings_growth': row[6]
        }
    else:
        print(f"Fetching fresh data for {symbol}")
        if check_daily_quota():
            return get_company_fundamentals(symbol)  # Fetch from API
        else:
            return None  # Quota exceeded
```

**Benefit**: Backtesting doesn't burn through API quota (uses cached data)

---

## Integration with Trading Bot

### Weekly Universe Refresh (Sunday 6 PM)
```python
import schedule

def refresh_fundamental_universe():
    """Run fundamental screener on universe (weekly task)"""
    
    # Load candidate tickers (e.g., S&P 500)
    candidates = pd.read_csv('sp500_tickers.csv')['Symbol'].tolist()
    
    # Screen 25 stocks per day (free tier limit)
    # Full S&P 500 would take 500/25 = 20 days
    # Recommendation: Start with top 100 by market cap
    
    universe = build_fundamental_universe(candidates[:25])
    
    print(f"Fundamental universe updated: {len(universe)} qualified stocks")

# Run every Sunday at 6 PM
schedule.every().sunday.at("18:00").do(refresh_fundamental_universe)
```

---

## Alternative: Financial Modeling Prep

If Alpha Vantage's free tier is too restrictive, consider **Financial Modeling Prep** (https://financialmodelingprep.com/).

**Pros**:
- Free tier: 250 calls/day (10x Alpha Vantage)
- Comprehensive fundamental data
- Better documentation

**Example**:
```python
import requests

def get_fmp_fundamentals(symbol):
    """Fetch fundamentals from Financial Modeling Prep"""
    
    url = f"https://financialmodelingprep.com/api/v3/profile/{symbol}"
    params = {'apikey': os.getenv('FMP_API_KEY')}
    
    response = requests.get(url, params=params)
    data = response.json()[0]
    
    return {
        'symbol': data['symbol'],
        'market_cap': data['mktCap'],
        'roe': data.get('roe', 0) * 100,
        'pb_ratio': data.get('priceToBook', 0),
        'sector': data['sector']
    }
```

---

## Error Handling

### Common Errors

**1. Rate Limit Exceeded**
```python
response = requests.get(url, params=params)

if 'Note' in response.json():
    print("ERROR: Alpha Vantage rate limit exceeded")
    print("Consider upgrading plan or using cached data")
```

**2. Invalid Symbol**
```python
data = response.json()

if not data or 'Symbol' not in data:
    print(f"ERROR: {symbol} not found or invalid")
```

**3. Missing Data Fields**
```python
roe = data.get('ReturnOnEquityTTM', None)

if roe is None or roe == 'None':
    print(f"WARNING: {symbol} missing ROE data, excluding from universe")
```

---

## Testing Checklist

### Before Integration
- [ ] API key working (test with `OVERVIEW` for AAPL)
- [ ] Fundamental filters correctly implemented
- [ ] Daily quota tracker prevents overuse
- [ ] Cache reduces redundant API calls
- [ ] Backup data source ready (FMP or manual CSV)

---

## Useful References
- **API Docs**: https://www.alphavantage.co/documentation/
- **Premium Plans**: https://www.alphavantage.co/premium/
- **Support**: https://www.alphavantage.co/support/#support

---

## Next Steps
1. Sign up for Alpha Vantage: https://www.alphavantage.co/support/#api-key
2. Test `OVERVIEW` on AAPL, MSFT, GOOGL
3. Implement SQLite cache for fundamental data
4. Screen top 25 stocks by market cap (S&P 500)
5. Consider upgrading to paid tier or switching to FMP
