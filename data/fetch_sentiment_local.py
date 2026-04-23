import os
import sys
import sqlite3
import logging
from datetime import datetime, timezone
from pathlib import Path
import yfinance as yf
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# Configuration
REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH   = REPO_ROOT / "trading_bot.db"

# Setup logging
LOG_FILE = REPO_ROOT / "logs" / "paper_trading.log"
os.makedirs(LOG_FILE.parent, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stdout)]
)

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
    try:
        rows = conn.execute("SELECT symbol FROM fundamental_universe ORDER BY symbol").fetchall()
        return [r[0] for r in rows]
    except sqlite3.OperationalError:
        return []

def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    setup_database(conn)

    tickers = get_universe_tickers(conn)
    if not tickers:
        print("fundamental_universe is empty. Run fundamental fetcher first.")
        conn.close()
        sys.exit(0)

    print("Local NLP Sentiment Screener — Yahoo Finance + VADER")
    print(f"Database : {DB_PATH}")
    print(f"Tickers  : {len(tickers)}\n")

    analyzer = SentimentIntensityAnalyzer()
    today_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    results = []

    for idx, symbol in enumerate(tickers):
        print(f"[{idx+1}/{len(tickers)}] Fetching news for {symbol}...", end="", flush=True)
        try:
            ticker = yf.Ticker(symbol)
            news = ticker.news
            
            if not news:
                print(" -> No news found.")
                results.append((symbol, 0.0, 0))
                continue

            scores = []
            for article in news:
                title = article.get("content", {}).get("title", "")
                if title:
                    score = analyzer.polarity_scores(title)['compound']
                    scores.append(score)
            
            if not scores:
                print(" -> No parseable titles found.")
                results.append((symbol, 0.0, 0))
                continue
                
            avg_score = sum(scores) / len(scores)
            buzz_ratio = len(scores)
            
            # Upsert into db
            conn.execute(
                """
                INSERT OR REPLACE INTO sentiment_cache (symbol, date, sentiment_score, buzz_ratio)
                VALUES (?, ?, ?, ?)
                """,
                (symbol, today_date, avg_score, buzz_ratio)
            )
            conn.commit()
            
            results.append((symbol, avg_score, buzz_ratio))
            print(f" -> Score: {avg_score:+.3f} (Buzz: {buzz_ratio})")

        except Exception as e:
            print(f" -> ERROR: {e}")
            results.append((symbol, 0.0, 0))

    conn.close()

    print("\n" + "=" * 60)
    print(f"SUMMARY: Local NLP Sentiment")
    print(f"{'Ticker':<8} | {'Avg Sentiment Score':>20} | {'Article Count':>15}")
    print("-" * 60)
    for sym, score, buzz in results:
        print(f"{sym:<8} | {score:>20.3f} | {buzz:>15}")
    print("=" * 60)

if __name__ == "__main__":
    main()