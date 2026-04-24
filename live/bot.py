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

import finnhub
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

# Validate required API keys on startup
_REQUIRED_KEYS = ('ALPACA_API_KEY', 'ALPACA_SECRET_KEY', 'FINNHUB_API_KEY')
for _k in _REQUIRED_KEYS:
    if not os.getenv(_k):
        logging.critical(f"Missing required env var: {_k}")
        sys.exit(1)


class TradingBot:
    def __init__(self):
        self.api_key = os.getenv('ALPACA_API_KEY')
        self.secret_key = os.getenv('ALPACA_SECRET_KEY')
        self.finnhub_key = os.getenv('FINNHUB_API_KEY')

        self.trading_client = TradingClient(self.api_key, self.secret_key, paper=True)
        self.data_client = StockHistoricalDataClient(self.api_key, self.secret_key)
        self.finnhub_client = finnhub.Client(api_key=self.finnhub_key)

        self.risk_per_trade = 0.025  # 2.5% risk per trade
        self.stop_loss_atr_multiplier = 2.5

        self._init_schema()

        self.pending_orders = []  # In-memory mirror, synced to DB

        logging.info("Trading Bot initialized.")

    def _get_conn(self):
        return sqlite3.connect(DB_PATH)

    def _init_schema(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sentiment_cache (
                    symbol          TEXT,
                    date            TEXT,
                    sentiment_score REAL,
                    buzz_ratio      INTEGER,
                    PRIMARY KEY (symbol, date)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pending_orders (
                    symbol      TEXT PRIMARY KEY,
                    queued_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS portfolio_state (
                    key   TEXT PRIMARY KEY,
                    value REAL
                )
            """)

    def get_active_universe(self):
        """Query fundamental_universe for symbols and sectors."""
        with self._get_conn() as conn:
            try:
                cursor = conn.execute("SELECT symbol, sector FROM fundamental_universe")
                return {row[0]: row[1] for row in cursor.fetchall()}
            except sqlite3.OperationalError:
                logging.error("fundamental_universe table does not exist.")
                return {}

    def get_sentiment(self, symbol: str) -> float:
        """Query sentiment_cache for the latest sentiment score."""
        with self._get_conn() as conn:
            try:
                row = conn.execute(
                    "SELECT sentiment_score FROM sentiment_cache WHERE symbol = ? ORDER BY date DESC LIMIT 1",
                    (symbol,)
                ).fetchone()
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

    def _check_macro_drawdown(self) -> bool:
        """Return True if drawdown from peak exceeds 15% (pause new entries)."""
        try:
            account = self.trading_client.get_account()
            equity = float(account.equity)
        except Exception as e:
            logging.error(f"Could not fetch account for drawdown check: {e}")
            return False

        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT value FROM portfolio_state WHERE key = 'peak_equity'"
            ).fetchone()
            peak = float(row[0]) if row else 0.0

            if equity > peak:
                peak = equity
                conn.execute(
                    "INSERT OR REPLACE INTO portfolio_state (key, value) VALUES ('peak_equity', ?)",
                    (peak,)
                )

        if peak > 0:
            drawdown_pct = ((peak - equity) / peak) * 100
            if drawdown_pct > 15.0:
                logging.critical(
                    f"MACRO DRAWDOWN PAUSE: equity {equity:.2f} is {drawdown_pct:.2f}% below peak {peak:.2f}. Skipping new entries."
                )
                return True
        return False

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

        # Macro drawdown pause
        if self._check_macro_drawdown():
            return

        universe = self.get_active_universe()
        tickers = list(universe.keys())
        if not tickers:
            logging.warning("No active universe found.")
            return

        bars_df = self.fetch_historical_batch(tickers)
        if bars_df is None or bars_df.empty:
            logging.error("Failed to fetch historical data.")
            return

        new_signals = []
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
                new_signals.append(symbol)

        # Persist pending orders to DB (and mirror in memory)
        with self._get_conn() as conn:
            conn.execute("DELETE FROM pending_orders")
            for sym in new_signals:
                conn.execute(
                    "INSERT OR REPLACE INTO pending_orders (symbol) VALUES (?)",
                    (sym,)
                )
        self.pending_orders = list(new_signals)

        logging.info(f"Queue updated. Pending Orders: {self.pending_orders}")

    def job_populate_sentiment(self):
        """Run daily at 3:00 PM ET: fetch Finnhub company_news, score headlines with VADER."""
        logging.info("--- Job: Sentiment Refresh (Finnhub company_news + VADER) ---")

        tickers = list(self.get_active_universe().keys())
        if not tickers:
            logging.warning("Sentiment refresh: fundamental_universe is empty, skipping.")
            return

        analyzer = SentimentIntensityAnalyzer()
        today_dt = datetime.now(pytz.utc)
        from_dt = today_dt - timedelta(days=7)
        today_str = today_dt.strftime('%Y-%m-%d')
        from_str = from_dt.strftime('%Y-%m-%d')

        ok, skipped, errors = 0, 0, 0

        with self._get_conn() as conn:
            for symbol in tickers:
                try:
                    news = self.finnhub_client.company_news(symbol, _from=from_str, to=today_str) or []
                    headlines = [a['headline'] for a in news if a.get('headline')]

                    if not headlines:
                        logging.info(f"{symbol}: no headlines, skipping.")
                        skipped += 1
                        time.sleep(0.5)
                        continue

                    scores = [analyzer.polarity_scores(h)['compound'] for h in headlines]
                    avg_score = sum(scores) / len(scores)
                    buzz_ratio = len(headlines)

                    conn.execute(
                        "INSERT OR REPLACE INTO sentiment_cache "
                        "(symbol, date, sentiment_score, buzz_ratio) VALUES (?, ?, ?, ?)",
                        (symbol, today_str, float(avg_score), int(buzz_ratio)),
                    )
                    logging.info(f"{symbol}: score={avg_score:+.3f}, buzz={buzz_ratio}")
                    ok += 1
                except Exception as e:
                    logging.error("Sentiment fetch failed for %s: %s", symbol, e)
                    errors += 1

                time.sleep(0.5)

        logging.info(
            "Sentiment refresh completed: %d updated, %d no-news, %d errors (total %d tickers).",
            ok, skipped, errors, len(tickers),
        )

    def _load_pending_orders(self) -> list:
        with self._get_conn() as conn:
            rows = conn.execute("SELECT symbol FROM pending_orders").fetchall()
        return [r[0] for r in rows]

    def _delete_pending_order(self, symbol: str):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM pending_orders WHERE symbol = ?", (symbol,))

    def job_execute_orders(self):
        """Run daily at 10:15 AM ET to execute queued orders."""
        logging.info("--- Job: Executing Queued Orders ---")

        pending = self._load_pending_orders()
        self.pending_orders = list(pending)

        if not pending:
            logging.info("No pending orders to execute.")
            return

        self.check_session_kill_switch()

        account = self.trading_client.get_account()
        equity = float(account.equity)

        universe = self.get_active_universe()
        sector_exposure = self.get_sector_exposure(universe)

        bars_df = self.fetch_historical_batch(pending, lookback_days=30)

        if bars_df is None or bars_df.empty:
            logging.error("Failed to fetch historical data for order execution.")
            return

        for symbol in pending:
            try:
                df = bars_df.loc[symbol].copy()
            except KeyError:
                logging.warning(f"Could not fetch recent data for {symbol}, skipping execution.")
                self._delete_pending_order(symbol)
                continue

            if len(df) < 15:
                logging.warning(f"Not enough data for ATR calculation for {symbol}, skipping.")
                self._delete_pending_order(symbol)
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

                    pos_size = share_qty * current_price
                    sector_exposure[sector] = current_sec_exp + pos_size

                except Exception as e:
                    logging.error(f"Failed to submit order for {symbol}: {str(e)}")
            else:
                logging.info(f"Skipping {symbol}: Sector limit exceeded or invalid size.")

            self._delete_pending_order(symbol)

        self.pending_orders = []
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

        last_kill_switch_check = None

        while True:
            now_et = datetime.now(eastern)
            is_weekday = now_et.weekday() < 5
            today_str = now_et.strftime('%Y-%m-%d')

            if is_weekday:
                # 3:00 PM ET — Sentiment refresh
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

                # Periodic kill-switch check during market hours (every 5 min)
                if self.check_market_hours():
                    if last_kill_switch_check is None or \
                       (now_et - last_kill_switch_check) >= timedelta(minutes=5):
                        try:
                            self.check_session_kill_switch()
                        except Exception as e:
                            logging.error(f"Kill switch check failed: {e}")
                        last_kill_switch_check = now_et

            time.sleep(30)


def main():
    bot = TradingBot()
    bot.run()

if __name__ == "__main__":
    main()
