import os
import sys
import sqlite3
import time
import requests
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Configuration
REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "trading_bot.db"
ENV_PATH = REPO_ROOT / ".env"
AV_BASE_URL = "https://www.alphavantage.co/query"
CALL_DELAY_S = 12

# Setup logging
LOG_FILE = REPO_ROOT / "logs" / "paper_trading.log"
os.makedirs(LOG_FILE.parent, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stdout)]
)

def load_api_key() -> str:
    load_dotenv(ENV_PATH)
    key = os.getenv("ALPHA_VANTAGE_API_KEY")
    if not key:
        logging.error("ALPHA_VANTAGE_API_KEY not found in .env")
        sys.exit(1)
    return key

def setup_database(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sentiment_cache (
            symbol TEXT,
            date TEXT,
            sentiment_score REAL,
            buzz_ratio INTEGER,
            PRIMARY KEY (symbol, date)
        )
    ''')
    conn.commit()

def get_universe_tickers(conn: sqlite3.Connection) -> list[str]:
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT symbol FROM fundamental_universe")
        return [row[0] for row in cursor.fetchall()]
    except sqlite3.OperationalError:
        logging.error("fundamental_universe table does not exist.")
        return []

def fetch_sentiment_av(symbol: str, api_key: str):
    params = {
        'function': 'NEWS_SENTIMENT',
        'tickers': symbol,
        'limit': 50,
        'apikey': api_key
    }
    
    try:
        response = requests.get(AV_BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        logging.error(f"Error fetching sentiment for {symbol}: {e}")
        return None
        
    if 'Note' in data or 'Information' in data:
        logging.warning(f"API Rate limit hit or warning for {symbol}: {data}")
        return 'RATE_LIMIT'
        
    if 'feed' not in data:
        logging.warning(f"No feed data for {symbol}.")
        return None
        
    sentiment_scores = []
    for article in data['feed']:
        if 'ticker_sentiment' in article:
            for ts in article['ticker_sentiment']:
                if ts['ticker'] == symbol:
                    try:
                        score = float(ts['ticker_sentiment_score'])
                        sentiment_scores.append(score)
                    except ValueError:
                        pass
                        
    if not sentiment_scores:
        return None
        
    avg_sentiment = sum(sentiment_scores) / len(sentiment_scores)
    buzz_ratio = len(sentiment_scores)
    
    return {
        'score': avg_sentiment,
        'buzz': buzz_ratio
    }

def main() -> None:
    api_key = load_api_key()
    
    conn = sqlite3.connect(DB_PATH)
    setup_database(conn)
    
    tickers = get_universe_tickers(conn)
    if not tickers:
        logging.warning("No tickers found in fundamental_universe.")
        conn.close()
        return
        
    logging.info(f"Starting sentiment fetch for {len(tickers)} tickers: {', '.join(tickers)}")
    
    today_date = datetime.now().strftime('%Y-%m-%d')
    cursor = conn.cursor()
    
    success_count = 0
    
    for i, symbol in enumerate(tickers):
        logging.info(f"[{i+1}/{len(tickers)}] Fetching sentiment for {symbol}...")
        
        result = fetch_sentiment_av(symbol, api_key)
        
        if result == 'RATE_LIMIT':
            logging.error("Rate limit encountered. Stopping fetch.")
            break
            
        if result:
            cursor.execute('''
                INSERT OR REPLACE INTO sentiment_cache (symbol, date, sentiment_score, buzz_ratio)
                VALUES (?, ?, ?, ?)
            ''', (symbol, today_date, result['score'], result['buzz']))
            conn.commit()
            logging.info(f"  → Saved {symbol}: Score={result['score']:.3f}, Buzz={result['buzz']}")
            success_count += 1
        else:
            logging.info(f"  → No sentiment data found for {symbol}.")
            
        if i < len(tickers) - 1:
            logging.info(f"  (waiting {CALL_DELAY_S}s...)")
            time.sleep(CALL_DELAY_S)
            
    conn.close()
    
    logging.info(f"--- Sentiment Fetch Summary ---")
    logging.info(f"Successfully processed: {success_count}/{len(tickers)}")

if __name__ == "__main__":
    main()