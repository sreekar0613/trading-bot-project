import os
import sys
import time
import logging
import sqlite3
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv
from pathlib import Path

# Load Alpaca keys from .env
load_dotenv()

import yfinance as yf
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

# Import indicators
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(REPO_ROOT))
from indicators.technical import (
    calculate_rsi, calculate_macd, calculate_bollinger, calculate_ema, calculate_atr
)

# Setup logging
LOG_FILE = REPO_ROOT / 'logs' / 'paper_trading.log'
os.makedirs(LOG_FILE.parent, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stdout)]
)

DB_PATH = REPO_ROOT / "trading_bot.db"

class TradingBot:
    def __init__(self):
        self.api_key = os.getenv('ALPACA_API_KEY')
        self.secret_key = os.getenv('ALPACA_SECRET_KEY')
        
        if not self.api_key or not self.secret_key:
            logging.error("Alpaca API keys missing in .env")
            raise ValueError("Alpaca API keys are missing in .env file.")
            
        self.trading_client = TradingClient(self.api_key, self.secret_key, paper=True)
        self.data_client = StockHistoricalDataClient(self.api_key, self.secret_key)
        
        self.risk_per_trade = 0.025  # 2.5% risk per trade
        self.stop_loss_atr_multiplier = 2.5
        
        self.db_conn = sqlite3.connect(DB_PATH)
        
        self.pending_orders = [] # Store orders overnight
        
        logging.info("Trading Bot initialized.")
        
    def __del__(self):
        if hasattr(self, 'db_conn'):
            self.db_conn.close()

    def get_active_universe(self):
        """Query fundamental_universe for symbols and sectors."""
        cursor = self.db_conn.cursor()
        try:
            cursor.execute("SELECT symbol, sector FROM fundamental_universe")
            rows = cursor.fetchall()
            return {row[0]: row[1] for row in rows}
        except sqlite3.OperationalError:
            logging.error("fundamental_universe table does not exist.")
            return {}

    def get_sentiment(self, symbol: str) -> float:
        """Query sentiment_cache for the latest sentiment score."""
        cursor = self.db_conn.cursor()
        try:
            cursor.execute(
                "SELECT sentiment_score FROM sentiment_cache WHERE symbol = ? ORDER BY date DESC LIMIT 1", 
                (symbol,)
            )
            row = cursor.fetchone()
            if row:
                return float(row[0])
        except sqlite3.OperationalError:
            pass
        return 0.0
        
    def check_market_hours(self) -> bool:
        eastern = pytz.timezone('US/Eastern')
        now_et = datetime.now(eastern)
        
        if now_et.weekday() >= 5:
            return False
            
        market_open = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
        
        return market_open <= now_et <= market_close

    def check_session_kill_switch(self):
        account = self.trading_client.get_account()
        equity = float(account.equity)
        last_equity = float(account.last_equity)
        
        if last_equity > 0:
            daily_pl_pct = ((equity - last_equity) / last_equity) * 100
            logging.info(f"Current Daily P&L: {daily_pl_pct:.2f}%")
            
            if daily_pl_pct < -5.0:
                logging.critical(f"KILL SWITCH TRIGGERED! Daily P&L is {daily_pl_pct:.2f}% (exceeds -5%).")
                self.trading_client.cancel_orders()
                self.trading_client.close_all_positions(cancel_orders=True)
                logging.critical("All positions closed and orders cancelled. Exiting bot.")
                sys.exit(1)

    def calculate_position_size(self, price: float, atr_value: float, equity: float, symbol: str, sector: str, current_sector_exposure: float) -> float:
        risk_amount = equity * self.risk_per_trade
        stop_distance = atr_value * self.stop_loss_atr_multiplier
        
        if stop_distance <= 0:
            return 0.0
            
        share_quantity = risk_amount / stop_distance
        pos_size = share_quantity * price
        
        # Hard cap 15%
        if pos_size > equity * 0.15:
            pos_size = equity * 0.15
            
        # Sector check 25%
        if current_sector_exposure + pos_size > equity * 0.25:
            available_room = (equity * 0.25) - current_sector_exposure
            if available_room <= 0:
                return 0.0
            else:
                pos_size = min(pos_size, available_room)
                
        return pos_size / price

    def get_sector_exposure(self, sectors: dict):
        positions = self.trading_client.get_all_positions()
        exposure = {}
        for p in positions:
            sym = p.symbol
            val = float(p.market_value)
            sec = sectors.get(sym, 'Unknown')
            exposure[sec] = exposure.get(sec, 0.0) + val
        return exposure

    def fetch_historical_batch(self, tickers: list[str], lookback_days: int = 365):
        end_time = datetime.now()
        start_time = end_time - timedelta(days=lookback_days)
        
        request = StockBarsRequest(
            symbol_or_symbols=tickers,
            timeframe=TimeFrame.Day,
            start=start_time,
            end=end_time
        )
        
        try:
            bars = self.data_client.get_stock_bars(request)
            return bars.df
        except Exception as e:
            logging.error(f"Failed to fetch data: {e}")
            return None

    def job_scan_signals(self):
        """Run daily at 4:05 PM ET to generate signals for the next morning."""
        logging.info("--- Job: Scanning Signals ---")
        self.pending_orders = [] # Clear the queue
        
        universe = self.get_active_universe()
        tickers = list(universe.keys())
        if not tickers:
            logging.warning("No active universe found.")
            return
            
        bars_df = self.fetch_historical_batch(tickers)
        if bars_df is None or bars_df.empty:
             logging.error("Failed to fetch historical data.")
             return
             
        for symbol in tickers:
            sentiment = self.get_sentiment(symbol)
            if sentiment <= 0:
                continue
                
            try:
                df = bars_df.loc[symbol].copy()
            except KeyError:
                continue
                
            if len(df) < 200:
                continue
                
            # Calculate Indicators
            rsi = calculate_rsi(df['close'])
            macd_data = calculate_macd(df['close'])
            bb_data = calculate_bollinger(df['close'])
            ema200 = calculate_ema(df['close'], period=200)
            
            df['rsi'] = rsi
            df['macd_hist'] = macd_data['histogram']
            df['bb_lower'] = bb_data['lower']
            df['ema200'] = ema200
            
            if len(df) < 10:
                continue
                
            last_10 = df.iloc[-10:]
            current = df.iloc[-1]
            prev = df.iloc[-2]
            
            macd_trigger = (current['macd_hist'] > 0) and (prev['macd_hist'] <= 0)
            rsi_context = (last_10['rsi'] < 35).any()
            bb_context = (last_10['close'] < last_10['bb_lower'] * 1.01).any()
            trend_filter = current['close'] > current['ema200']
            
            if trend_filter and rsi_context and bb_context and macd_trigger:
                logging.info(f"BUY Signal generated for {symbol}")
                self.pending_orders.append(symbol)

        logging.info(f"Queue updated. Pending Orders: {self.pending_orders}")

    def job_populate_sentiment(self):
        """Run daily at 3:00 PM ET to refresh sentiment_cache before signal scan."""
        logging.info("--- Job: Sentiment Refresh ---")

        # Ensure table exists (safe if already present)
        self.db_conn.execute("""
            CREATE TABLE IF NOT EXISTS sentiment_cache (
                symbol          TEXT,
                date            TEXT,
                sentiment_score REAL,
                buzz_ratio      INTEGER,
                PRIMARY KEY (symbol, date)
            )
        """)
        self.db_conn.commit()

        tickers = list(self.get_active_universe().keys())
        if not tickers:
            logging.warning("Sentiment refresh: fundamental_universe is empty, skipping.")
            return

        analyzer = SentimentIntensityAnalyzer()
        today = datetime.now(pytz.utc).strftime("%Y-%m-%d")
        ok, skipped, errors = 0, 0, 0

        for symbol in tickers:
            try:
                news = yf.Ticker(symbol).news or []
                scores = [
                    analyzer.polarity_scores(a.get("content", {}).get("title", ""))["compound"]
                    for a in news
                    if a.get("content", {}).get("title", "")
                ]
                if not scores:
                    skipped += 1
                    continue

                avg_score = sum(scores) / len(scores)
                self.db_conn.execute(
                    "INSERT OR REPLACE INTO sentiment_cache "
                    "(symbol, date, sentiment_score, buzz_ratio) VALUES (?, ?, ?, ?)",
                    (symbol, today, avg_score, len(scores)),
                )
                ok += 1
            except Exception as e:
                logging.error("Sentiment fetch failed for %s: %s", symbol, e)
                errors += 1

        self.db_conn.commit()
        logging.info(
            "Sentiment refresh completed: %d updated, %d no-news, %d errors (total %d tickers).",
            ok, skipped, errors, len(tickers),
        )

    def job_execute_orders(self):
        """Run daily at 10:15 AM ET to execute queued orders."""
        logging.info("--- Job: Executing Queued Orders ---")
        
        if not self.pending_orders:
            logging.info("No pending orders to execute.")
            return
            
        self.check_session_kill_switch()
        
        account = self.trading_client.get_account()
        equity = float(account.equity)
        
        universe = self.get_active_universe()
        sector_exposure = self.get_sector_exposure(universe)
        
        # Need current price and ATR to calculate position size safely
        bars_df = self.fetch_historical_batch(self.pending_orders, lookback_days=30)
        
        if bars_df is None or bars_df.empty:
            logging.error("Failed to fetch historical data for order execution.")
            return

        for symbol in self.pending_orders:
             try:
                 df = bars_df.loc[symbol].copy()
             except KeyError:
                 logging.warning(f"Could not fetch recent data for {symbol}, skipping execution.")
                 continue
                 
             if len(df) < 15:
                 logging.warning(f"Not enough data for ATR calculation for {symbol}, skipping.")
                 continue

             atr = calculate_atr(df['high'], df['low'], df['close'])
             current_price = df.iloc[-1]['close']
             current_atr = atr.iloc[-1]
             
             sector = universe.get(symbol, 'Unknown')
             current_sec_exp = sector_exposure.get(sector, 0.0)
             
             share_qty = self.calculate_position_size(current_price, current_atr, equity, symbol, sector, current_sec_exp)
             
             if share_qty > 0:
                 try:
                     order_req = MarketOrderRequest(
                         symbol=symbol,
                         qty=round(share_qty, 4),
                         side=OrderSide.BUY,
                         time_in_force=TimeInForce.DAY
                     )
                     self.trading_client.submit_order(order_req)
                     logging.info(f"Executed Order: BUY {round(share_qty, 4)} shares of {symbol}")
                     
                     # Update exposure to reflect the execution
                     pos_size = share_qty * current_price
                     sector_exposure[sector] = current_sec_exp + pos_size
                     
                 except Exception as e:
                     logging.error(f"Failed to submit order for {symbol}: {str(e)}")
             else:
                 logging.info(f"Skipping {symbol}: Sector limit exceeded or invalid size.")
                 
        self.pending_orders = [] # Clear after processing
        logging.info("Execution job completed.")

    def run(self):
        """Infinite loop to process timezone-aware scheduling."""
        eastern = pytz.timezone('US/Eastern')
        logging.info("Starting autonomous bot execution loop...")
        
        executed_today = {
            'sentiment': None,
            'scan': None,
            'execute': None,
        }

        while True:
            now_et = datetime.now(eastern)
            is_weekday = now_et.weekday() < 5
            today_str = now_et.strftime('%Y-%m-%d')

            if is_weekday:
                # 3:00 PM ET — Sentiment refresh (must run before 4:05 PM scan)
                if now_et.hour == 15 and now_et.minute == 0:
                    if executed_today['sentiment'] != today_str:
                        self.job_populate_sentiment()
                        executed_today['sentiment'] = today_str

                # 4:05 PM ET Scan
                if now_et.hour == 16 and now_et.minute == 5:
                    if executed_today['scan'] != today_str:
                        self.job_scan_signals()
                        executed_today['scan'] = today_str

                # 10:15 AM ET Execute
                if now_et.hour == 10 and now_et.minute == 15:
                    if executed_today['execute'] != today_str:
                        self.job_execute_orders()
                        executed_today['execute'] = today_str
            
            # Sleep 30 seconds to prevent CPU spinning, precise enough to hit a 1-minute window
            time.sleep(30)


def main():
    bot = TradingBot()
    bot.run()

if __name__ == "__main__":
    main()