# Finnhub API Integration — Skill Documentation

## Overview
Finnhub provides real-time and historical financial data, including news sentiment analysis. Use for sentiment scoring as a confirmation filter before executing trades.

**Official Docs**: https://finnhub.io/docs/api

---

## Authentication

### API Key
- **Free Tier**: 60 API calls/minute, limited features
- **Paid Tiers**: Higher rate limits, premium data sources

**Sign Up**: https://finnhub.io/register

### Installation
```bash
pip install finnhub-python
```

### Initialization
```python
import finnhub
import os

# Setup client
finnhub_client = finnhub.Client(api_key=os.getenv('FINNHUB_API_KEY'))
```

**Security**: Store key in `.env` file, never hardcode

---

## Key Endpoints

### 1. Company News Sentiment
**Purpose**: Get sentiment scores for news articles about a company

**Endpoint**: `GET /news-sentiment`

```python
# Get sentiment for Apple (AAPL)
sentiment = finnhub_client.news_sentiment('AAPL')

print(f"Company Sentiment Score: {sentiment['companyNewsScore']}")
print(f"Sector Average: {sentiment['sectorAverageBullishPercent']}")
print(f"Buzz (Articles Last Week): {sentiment['buzz']['articlesInLastWeek']}")
```

**Response Structure**:
```json
{
  "companyNewsScore": 0.6543,  // -1 (negative) to 1 (positive)
  "sectorAverageBullishPercent": 0.58,
  "buzz": {
    "articlesInLastWeek": 127,
    "weeklyAverage": 98.5,
    "buzz": 1.29  // Ratio of current to average buzz
  },
  "sentiment": {
    "bearishPercent": 0.25,
    "bullishPercent": 0.75
  }
}
```

**Trading Strategy Integration**:
- **Require** `companyNewsScore > 0` (positive sentiment)
- **Bonus signal**: `buzz > 1.2` (above-average news volume)
- **Red flag**: `bearishPercent > 0.60` (negative sentiment dominates)

---

### 2. Company News (Raw Articles)
**Purpose**: Retrieve individual news headlines and sources for manual analysis

**Endpoint**: `GET /company-news`

```python
from datetime import datetime, timedelta

# Get last 7 days of news for AAPL
end_date = datetime.now()
start_date = end_date - timedelta(days=7)

news = finnhub_client.company_news(
    'AAPL',
    _from=start_date.strftime('%Y-%m-%d'),
    to=end_date.strftime('%Y-%m-%d')
)

for article in news[:5]:  # First 5 articles
    print(f"{article['headline']}")
    print(f"  Source: {article['source']}")
    print(f"  Sentiment: {article.get('sentiment', 'N/A')}")
    print(f"  URL: {article['url']}\n")
```

**Response Fields**:
- `headline` — Article title
- `summary` — Brief description
- `source` — Publisher (e.g., "Reuters", "Bloomberg")
- `url` — Link to full article
- `datetime` — Unix timestamp
- `sentiment` — Optional sentiment score (if available)

**Use Case**: Debugging why sentiment score is positive/negative

---

### 3. Market News (General)
**Purpose**: Get broad market news (not company-specific)

**Endpoint**: `GET /news`

```python
# Get general market news (last 24 hours)
market_news = finnhub_client.general_news('general')

for article in market_news[:5]:
    print(f"{article['headline']} — {article['source']}")
```

**Categories**:
- `general` — All market news
- `forex` — Currency markets
- `crypto` — Cryptocurrency news
- `merger` — M&A activity

**Use Case**: Identify macro events that might trigger kill switch (e.g., Fed rate decision, geopolitical crisis)

---

## Sentiment Scoring Logic

### Rolling 7-Day Average (Strategy Requirement)
```python
from datetime import datetime, timedelta
import numpy as np

def get_7day_sentiment_avg(symbol):
    """Calculate 7-day rolling average of sentiment scores"""
    
    sentiment_scores = []
    
    for i in range(7):
        date = datetime.now() - timedelta(days=i)
        
        try:
            # Finnhub sentiment endpoint (returns daily aggregate)
            sentiment = finnhub_client.news_sentiment(symbol)
            score = sentiment['companyNewsScore']
            sentiment_scores.append(score)
        except Exception as e:
            print(f"Error fetching sentiment for {symbol}: {e}")
            continue
    
    if len(sentiment_scores) == 0:
        return None  # No data available
    
    avg_sentiment = np.mean(sentiment_scores)
    return avg_sentiment

# Example usage
aapl_sentiment = get_7day_sentiment_avg('AAPL')

if aapl_sentiment and aapl_sentiment > 0:
    print(f"AAPL 7-day sentiment: {aapl_sentiment:.3f} (POSITIVE — safe to trade)")
else:
    print(f"AAPL 7-day sentiment: {aapl_sentiment:.3f} (NEGATIVE — skip)")
```

### Confidence Weighting (Advanced)
Some sentiment APIs provide confidence scores (0–1) indicating certainty of classification.

```python
def get_weighted_sentiment(symbol):
    """Weight sentiment by confidence level (if available)"""
    
    news = finnhub_client.company_news(
        symbol,
        _from=(datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'),
        to=datetime.now().strftime('%Y-%m-%d')
    )
    
    weighted_scores = []
    
    for article in news:
        if 'sentiment' in article and 'confidence' in article:
            score = article['sentiment']
            confidence = article['confidence']
            weighted_scores.append(score * confidence)
    
    if len(weighted_scores) == 0:
        return None
    
    return np.mean(weighted_scores)
```

**Rationale**: A sentiment score of 0.8 with 0.95 confidence is more reliable than 0.8 with 0.40 confidence

---

## Rate Limits & Caching

### Free Tier Limits
- **60 calls/minute** — Exceeded limit results in HTTP 429 error
- **30 calls/second** — Burst limit

### Best Practices
1. **Cache sentiment data** — Store in local database, refresh once per day
2. **Batch requests** — Fetch multiple symbols in parallel (up to rate limit)
3. **Handle 429 errors** — Exponential backoff retry logic

```python
import time
from requests.exceptions import HTTPError

def fetch_with_retry(symbol, max_retries=3):
    """Fetch sentiment with exponential backoff on rate limit"""
    
    for attempt in range(max_retries):
        try:
            sentiment = finnhub_client.news_sentiment(symbol)
            return sentiment
        except HTTPError as e:
            if e.response.status_code == 429:  # Rate limit exceeded
                wait_time = 2 ** attempt  # 1s, 2s, 4s
                print(f"Rate limit hit, retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise
    
    print(f"Failed to fetch sentiment for {symbol} after {max_retries} retries")
    return None
```

---

## Integration with Trading Strategy

### Pre-Entry Sentiment Check
```python
def validate_sentiment(symbol):
    """Check if sentiment supports a long entry"""
    
    sentiment_7d = get_7day_sentiment_avg(symbol)
    
    if sentiment_7d is None:
        print(f"WARNING: No sentiment data for {symbol}, skipping")
        return False
    
    if sentiment_7d < 0:
        print(f"SKIP: {symbol} has negative sentiment ({sentiment_7d:.3f})")
        return False
    
    print(f"PASS: {symbol} sentiment is positive ({sentiment_7d:.3f})")
    return True

# In main trading loop
if validate_sentiment('AAPL') and check_technical_signals('AAPL'):
    execute_buy_order('AAPL')
```

### Database Schema (Local Caching)
```sql
CREATE TABLE sentiment_cache (
    symbol TEXT NOT NULL,
    date DATE NOT NULL,
    sentiment_score REAL,
    buzz_ratio REAL,
    articles_count INTEGER,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, date)
);

-- Example insert
INSERT INTO sentiment_cache (symbol, date, sentiment_score, buzz_ratio, articles_count)
VALUES ('AAPL', '2024-04-22', 0.654, 1.29, 127);
```

**Refresh Strategy**:
- Update cache daily at 4:00 PM ET (before signal generation)
- Query cache instead of API during backtesting
- Re-fetch only if cache is > 24 hours old

---

## Alternative: Alpha Vantage Sentiment

If Finnhub rate limits are restrictive, Alpha Vantage offers similar sentiment analysis.

### Alpha Vantage Endpoint
```python
import requests

def get_alpha_vantage_sentiment(symbol):
    """Fetch sentiment from Alpha Vantage (alternative to Finnhub)"""
    
    url = f"https://www.alphavantage.co/query"
    params = {
        'function': 'NEWS_SENTIMENT',
        'tickers': symbol,
        'apikey': os.getenv('ALPHA_VANTAGE_API_KEY')
    }
    
    response = requests.get(url, params=params)
    data = response.json()
    
    if 'feed' not in data:
        return None
    
    # Calculate average sentiment from recent articles
    scores = [float(article['overall_sentiment_score']) for article in data['feed']]
    return np.mean(scores) if scores else None
```

**Pros**:
- Free tier: 25 calls/day (sufficient for daily updates)
- More detailed sentiment breakdowns

**Cons**:
- Lower rate limit than Finnhub
- Slower response times

---

## Error Handling

### Common Errors

**1. Symbol Not Found**
```python
try:
    sentiment = finnhub_client.news_sentiment('INVALID_TICKER')
except Exception as e:
    if "not found" in str(e).lower():
        print("ERROR: Symbol does not exist")
```

**2. Rate Limit Exceeded**
```python
try:
    sentiment = finnhub_client.news_sentiment('AAPL')
except HTTPError as e:
    if e.response.status_code == 429:
        print("Rate limit exceeded, implement caching or upgrade plan")
```

**3. No News Available**
```python
sentiment = finnhub_client.news_sentiment('OBSCURE_TICKER')

if sentiment['buzz']['articlesInLastWeek'] == 0:
    print("WARNING: No recent news, sentiment unreliable")
```

---

## Testing Checklist

### Before Integrating with Bot
- [ ] API key working (test with `news_sentiment('AAPL')`)
- [ ] 7-day rolling average calculation correct
- [ ] Cache implemented (avoid repeated API calls)
- [ ] Rate limit retry logic tested
- [ ] Fallback to Alpha Vantage if Finnhub fails

---

## Useful References
- **API Docs**: https://finnhub.io/docs/api/news-sentiment
- **Python SDK**: https://github.com/Finnhub-Stock-API/finnhub-python
- **Dashboard**: https://finnhub.io/dashboard (monitor API usage)

---

## Next Steps
1. Sign up for Finnhub: https://finnhub.io/register
2. Generate API key
3. Test `news_sentiment()` on AAPL, MSFT, TSLA
4. Implement 7-day rolling average function
5. Create SQLite cache table for sentiment scores
