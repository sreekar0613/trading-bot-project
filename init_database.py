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

