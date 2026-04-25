import os
import sys
import time
import random
import logging
import sqlite3
import json
from datetime import datetime, timedelta, date
import pytz
from dotenv import load_dotenv
from pathlib import Path

import finnhub
import yfinance as yf
import openai
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

# Import indicators
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(REPO_ROOT))

# Load Alpaca keys from .env (absolute path so systemd CWD doesn't matter)
load_dotenv(REPO_ROOT / ".env")
from indicators.technical import (
    calculate_rsi, calculate_macd, calculate_bollinger, calculate_ema, calculate_atr
)
from config import (
    MAX_DAILY_LOSS_PCT, API_MAX_RETRIES, API_BACKOFF_BASE, EARNINGS_WINDOW_DAYS,
    VIX_THRESHOLD, SPY_TREND_LOOKBACK, RISK_PER_TRADE
)
from strategy.regime import MarketRegimeDetector

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
_REQUIRED_KEYS = ('ALPACA_API_KEY', 'ALPACA_SECRET_KEY', 'FINNHUB_API_KEY', 'OPENAI_API_KEY')
for _k in _REQUIRED_KEYS:
    if not os.getenv(_k):
        logging.critical(f"Missing required env var: {_k}")
        sys.exit(1)

openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def _get_gpt_sentiment(headline: str) -> float:
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": "You are a highly accurate financial sentiment analyzer. Analyze the following news headline. Classify its short-term impact on the mentioned company's stock price as Positive (1.0), Neutral (0.0), or Negative (-1.0). Respond ONLY with a valid JSON object in this exact format: {\"score\": <float>}."
                },
                {"role": "user", "content": headline}
            ],
            timeout=10.0
        )
        content = response.choices[0].message.content
        if content:
            data = json.loads(content)
            return float(data.get("score", 0.0))
        return 0.0
    except Exception as e:
        logging.error(f"GPT sentiment analysis failed for '{headline}': {e}")
        return 0.0


class TradingBot:
    def __init__(self):
        self.api_key = os.getenv('ALPACA_API_KEY')
        self.secret_key = os.getenv('ALPACA_SECRET_KEY')
        self.finnhub_key = os.getenv('FINNHUB_API_KEY')

        self.trading_client = TradingClient(self.api_key, self.secret_key, paper=True)
        self.data_client = StockHistoricalDataClient(self.api_key, self.secret_key)
        self.finnhub_client = finnhub.Client(api_key=self.finnhub_key)

        self.risk_per_trade = RISK_PER_TRADE
        self.stop_loss_atr_multiplier = 2.5

        self._init_schema()

        self.pending_orders = []  # In-memory mirror, synced to DB

        self.halted_until = None  # Date until which the bot is halted by circuit breaker

        logging.info("Trading Bot initialized.")

    def alpaca_call_with_backoff(self, func, *args, **kwargs):
        """Call an Alpaca API function with exponential backoff + jitter.

        Retries up to API_MAX_RETRIES times on any exception. Backoff delay is
        random.uniform(0, 1) * API_BACKOFF_BASE ** attempt. Re-raises the last
        exception if all retries are exhausted.
        """
        last_exc = None
        for attempt in range(API_MAX_RETRIES):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exc = e
                if attempt == API_MAX_RETRIES - 1:
                    logging.error(
                        f"Alpaca call {func.__name__} failed after {API_MAX_RETRIES} attempts: {e}"
                    )
                    raise
                delay = random.uniform(0, 1) * (API_BACKOFF_BASE ** attempt)
                logging.warning(
                    f"Alpaca call {func.__name__} failed (attempt {attempt + 1}/{API_MAX_RETRIES}): "
                    f"{e}. Retrying in {delay:.2f}s."
                )
                time.sleep(delay)
        raise last_exc  # unreachable, but keeps analyzers happy

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
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    paused BOOLEAN DEFAULT 0,
                    last_heartbeat TIMESTAMP,
                    open_position_count INTEGER DEFAULT 0,
                    halted_until TEXT,
                    peak_equity REAL,
                    current_regime INTEGER DEFAULT 2
                )
            """)
            conn.execute("INSERT OR IGNORE INTO portfolio_state (id) VALUES (1)")
            # In case the table exists without current_regime, try adding it
            try:
                conn.execute("ALTER TABLE portfolio_state ADD COLUMN current_regime INTEGER DEFAULT 2")
            except sqlite3.OperationalError:
                pass
            conn.execute("""
                CREATE TABLE IF NOT EXISTS earnings_calendar (
                    symbol         TEXT,
                    earnings_date  TEXT,
                    fetched_at     TEXT,
                    PRIMARY KEY (symbol, earnings_date)
                )
            """)

    def _is_paused(self) -> bool:
        """Query portfolio_state for the paused flag."""
        try:
            with self._get_conn() as conn:
                row = conn.execute("SELECT paused FROM portfolio_state WHERE id = 1").fetchone()
                return bool(row[0]) if row else False
        except Exception as e:
            logging.error(f"Failed to check paused state: {e}")
            return False

    def _update_system_state(self):
        """Update last_heartbeat and open_position_count in portfolio_state."""
        try:
            positions = self.alpaca_call_with_backoff(self.trading_client.get_all_positions)
            open_count = len(positions) if positions else 0
            with self._get_conn() as conn:
                conn.execute(
                    "UPDATE portfolio_state SET last_heartbeat = CURRENT_TIMESTAMP, open_position_count = ? WHERE id = 1",
                    (open_count,)
                )
        except Exception as e:
            logging.error(f"Failed to update system state: {e}")

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

    def fetch_earnings_calendar(self, symbol: str) -> tuple[bool, list[str]]:
        """Return (ok, dates) for upcoming earnings within the next 30 days.

        - (False, [])   — fetch failed or cache unusable; caller must fail-closed.
        - (True,  [])   — Finnhub confirmed no upcoming earnings; caller may allow.
        - (True,  [...])— earnings dates (YYYY-MM-DD); caller checks 3-day window.

        Uses SQLite cache refreshed at most weekly. A sentinel row
        ('9999-12-31') is written when Finnhub returns no earnings so cache
        freshness lookups still register "we checked today."
        """
        today = date.today()
        today_str = today.isoformat()
        cutoff_str = (today - timedelta(days=7)).isoformat()

        # Cache hit: any row for this symbol with fresh fetched_at means we
        # checked within the last 7 days.
        with self._get_conn() as conn:
            fresh = conn.execute(
                "SELECT 1 FROM earnings_calendar WHERE symbol = ? AND fetched_at >= ? LIMIT 1",
                (symbol, cutoff_str),
            ).fetchone()

            if fresh:
                rows = conn.execute(
                    "SELECT earnings_date FROM earnings_calendar "
                    "WHERE symbol = ? AND earnings_date >= ? "
                    "AND earnings_date != '9999-12-31'",
                    (symbol, today_str),
                ).fetchall()
                return True, [r[0] for r in rows]

        # Cache miss or stale — refetch from Finnhub
        try:
            end_str = (today + timedelta(days=30)).isoformat()
            resp = self.alpaca_call_with_backoff(
                self.finnhub_client.earnings_calendar,
                _from=today_str, to=end_str, symbol=symbol, international=False,
            )
        except Exception as e:
            logging.warning(f"Earnings calendar fetch failed for {symbol}: {e}")
            return False, []

        if not isinstance(resp, dict) or 'earningsCalendar' not in resp:
            logging.warning(f"Earnings calendar: unexpected response for {symbol}: {resp!r}")
            return False, []

        earnings_dates = [e['date'] for e in resp['earningsCalendar'] if e.get('date')]

        with self._get_conn() as conn:
            conn.execute("DELETE FROM earnings_calendar WHERE symbol = ?", (symbol,))
            if earnings_dates:
                for d in earnings_dates:
                    conn.execute(
                        "INSERT OR REPLACE INTO earnings_calendar "
                        "(symbol, earnings_date, fetched_at) VALUES (?, ?, ?)",
                        (symbol, d, today_str),
                    )
            else:
                # Sentinel row marks "checked, nothing upcoming" so cache freshness
                # lookups work even when there are no real earnings dates.
                conn.execute(
                    "INSERT OR REPLACE INTO earnings_calendar "
                    "(symbol, earnings_date, fetched_at) VALUES (?, '9999-12-31', ?)",
                    (symbol, today_str),
                )

        return True, earnings_dates

    def _is_within_earnings_window(
        self, earnings_dates: list[str], window_days: int = EARNINGS_WINDOW_DAYS
    ) -> tuple[bool, str]:
        """Return (True, matching_date) if any earnings_date falls within
        today-1 .. today+window_days (calendar days, inclusive)."""
        today = date.today()
        start = today - timedelta(days=1)
        end = today + timedelta(days=window_days)
        for d_str in earnings_dates:
            try:
                d = date.fromisoformat(d_str)
            except ValueError:
                continue
            if start <= d <= end:
                return True, d_str
        return False, ""

    def check_market_hours(self) -> bool:
        eastern = pytz.timezone('US/Eastern')
        now_et = datetime.now(eastern)

        if now_et.weekday() >= 5:
            return False

        market_open = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now_et.replace(hour=16, minute=0, second=0, microsecond=0)

        return market_open <= now_et <= market_close

    def check_session_kill_switch(self):
        account = self.alpaca_call_with_backoff(self.trading_client.get_account)
        equity = float(account.equity)
        last_equity = float(account.last_equity)

        if last_equity > 0:
            daily_pl_pct = ((equity - last_equity) / last_equity) * 100
            logging.info(f"Current Daily P&L: {daily_pl_pct:.2f}%")

            if daily_pl_pct < -5.0:
                logging.critical(f"KILL SWITCH TRIGGERED! Daily P&L is {daily_pl_pct:.2f}% (exceeds -5%).")
                self.alpaca_call_with_backoff(self.trading_client.cancel_orders)
                self.alpaca_call_with_backoff(self.trading_client.close_all_positions, cancel_orders=True)
                logging.critical("All positions closed and orders cancelled. Exiting bot.")
                sys.exit(1)

    def _persist_halted_until(self, value: str | None) -> None:
        """Mirror self.halted_until to portfolio_state so the FastAPI sidecar
        context endpoint can report the halted state. value is an ISO date string
        or None to clear."""
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "UPDATE portfolio_state SET halted_until = ? WHERE id = 1",
                    (value,)
                )
        except Exception as e:
            logging.error(f"Failed to persist halted_until={value}: {e}")

    def check_daily_loss_circuit_breaker(self) -> bool:
        """Circuit breaker: halt bot for the rest of the trading day if net daily
        PnL falls below -MAX_DAILY_LOSS_PCT. Returns True if breaker tripped."""
        try:
            account = self.alpaca_call_with_backoff(self.trading_client.get_account)
        except Exception as e:
            if self.check_market_hours():
                logging.critical(
                    f"Circuit breaker: could not fetch account during market hours: {e}. "
                    f"Fail-closed — halting until next trading day."
                )
                self.halted_until = date.today()
                self._persist_halted_until(self.halted_until.isoformat())
                return True
            logging.error(f"Circuit breaker: could not fetch account (market closed): {e}")
            return False

        last_equity = float(account.last_equity)
        if last_equity <= 0:
            return False

        equity = float(account.equity)
        daily_pl_pct = ((equity - last_equity) / last_equity) * 100
        threshold_pct = -(MAX_DAILY_LOSS_PCT * 100)

        if daily_pl_pct < threshold_pct:
            logging.critical(
                f"DAILY LOSS CIRCUIT BREAKER TRIGGERED! Daily P&L is {daily_pl_pct:.2f}% "
                f"(threshold {threshold_pct:.2f}%). Flattening positions and halting until next trading day."
            )
            try:
                self.alpaca_call_with_backoff(self.trading_client.cancel_orders)
                self.alpaca_call_with_backoff(self.trading_client.close_all_positions, cancel_orders=True)
            except Exception as e:
                logging.critical(f"Circuit breaker flatten failed: {e}")
            self.halted_until = date.today()
            self._persist_halted_until(self.halted_until.isoformat())
            return True

        return False

    def _check_macro_drawdown(self) -> bool:
        """Return True if drawdown from peak exceeds 15% (pause new entries)."""
        try:
            account = self.alpaca_call_with_backoff(self.trading_client.get_account)
            equity = float(account.equity)
        except Exception as e:
            logging.error(f"Could not fetch account for drawdown check: {e}")
            return False

        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT peak_equity FROM portfolio_state WHERE id = 1"
            ).fetchone()
            peak = float(row[0]) if row and row[0] is not None else 0.0

            if equity > peak:
                peak = equity
                conn.execute(
                    "UPDATE portfolio_state SET peak_equity = ? WHERE id = 1",
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

    def _check_regime_filter(self) -> bool:
        """Return True if SPY close < 200 EMA and VIX > threshold (risk-off)."""
        try:
            df = yf.download(['SPY', '^VIX'], period="2y", progress=False)
            if df.empty:
                logging.error("Regime filter: yfinance returned empty dataframe.")
                return False

            spy_close = df['Close']['SPY'].iloc[-1]
            vix_close = df['Close']['^VIX'].iloc[-1]
            spy_ema200 = df['Close']['SPY'].ewm(span=SPY_TREND_LOOKBACK, adjust=False).mean().iloc[-1]

            if vix_close > VIX_THRESHOLD and spy_close < spy_ema200:
                return True
            return False
        except Exception as e:
            logging.error(f"Regime filter check failed: {e}")
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
        positions = self.alpaca_call_with_backoff(self.trading_client.get_all_positions)
        exposure = {}
        for p in positions:
            sym = p.symbol
            val = float(p.market_value)
            sec = sectors.get(sym, 'Unknown')
            exposure[sec] = exposure.get(sec, 0.0) + val
        return exposure

    def fetch_historical_batch(self, tickers: list[str], lookback_days: int = 365):
        import pandas as pd
        end_time = datetime.now()
        start_time = end_time - timedelta(days=lookback_days)

        # Primary: yfinance (avoids IEX 'recent SIP data' errors on Alpaca free tier)
        logging.info(f"Fetching historical data via yfinance for {len(tickers)} ticker(s).")
        try:
            start_str = start_time.strftime('%Y-%m-%d')
            end_str = end_time.strftime('%Y-%m-%d')
            df = yf.download(tickers, start=start_str, end=end_str, progress=False)

            if df is None or df.empty:
                raise ValueError("yfinance returned empty dataframe")

            # Normalize yfinance dataframe to match Alpaca schema
            if isinstance(df.columns, pd.MultiIndex):
                try:
                    df = df.stack(level=1, future_stack=True)
                except TypeError:
                    df = df.stack(level=1)
                df.index.names = ['timestamp', 'symbol']
                df = df.swaplevel(0, 1)
            else:
                df['symbol'] = tickers[0]
                df = df.set_index('symbol', append=True)
                df = df.swaplevel(0, 1)
                df.index.names = ['symbol', 'timestamp']

            df.columns = [str(c).lower() for c in df.columns]

            # Align timezone to UTC to match Alpaca
            if df.index.levels[1].tz is None:
                df.index = df.index.set_levels(pd.to_datetime(df.index.levels[1]).tz_localize('UTC'), level=1)
            else:
                df.index = df.index.set_levels(pd.to_datetime(df.index.levels[1]).tz_convert('UTC'), level=1)

            return df
        except Exception as yf_e:
            logging.warning(f"yfinance failed ({yf_e}), falling back to Alpaca IEX.")

        # Fallback: Alpaca IEX free feed
        request = StockBarsRequest(
            symbol_or_symbols=tickers,
            timeframe=TimeFrame.Day,
            feed="iex",
            start=start_time,
            end=end_time
        )
        try:
            bars = self.alpaca_call_with_backoff(self.data_client.get_stock_bars, request)
            return bars.df
        except Exception as e:
            logging.error(f"Alpaca IEX fallback also failed: {e}")
            return None

    def job_scan_signals(self):
        """Run daily at 4:05 PM ET to generate signals for the next morning."""
        logging.info("--- Job: Scanning Signals ---")

        if self._is_paused():
            logging.info("System is paused via override. Skipping.")
            return

        if self.halted_until == date.today():
            logging.warning("Bot halted by daily loss circuit breaker — skipping signal scan.")
            return

        # Macro drawdown pause
        if self._check_macro_drawdown():
            return

        if self._check_regime_filter():
            logging.info("regime: risk-off, skipping entries")
            return

        try:
            spy_df = yf.download(['SPY'], period="2y", progress=False)
            detector = MarketRegimeDetector()
            current_regime = detector.predict(spy_df)
            detector.save()
            with self._get_conn() as conn:
                conn.execute("UPDATE portfolio_state SET current_regime = ? WHERE id = 1", (current_regime,))
            logging.info(f"Market Regime updated to State {current_regime}")
        except Exception as e:
            logging.error(f"Failed to update market regime: {e}")

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
            # Relaxed from 35→40 per Task #5 walk-forward validation (2026-04-25)
            rsi_context = (last_10['rsi'] < 40).any()
            bb_context = (last_10['close'] < last_10['bb_lower'] * 1.01).any()
            trend_filter = current['close'] > current['ema200']

            if trend_filter and rsi_context and bb_context and macd_trigger:
                ok, earnings_dates = self.fetch_earnings_calendar(symbol)
                if not ok:
                    logging.warning(
                        f"{symbol}: skipped — could not verify earnings calendar (fail-closed)"
                    )
                    continue
                in_window, match_date = self._is_within_earnings_window(earnings_dates)
                if in_window:
                    logging.info(
                        f"{symbol}: skipped — earnings within 3-day window ({match_date})"
                    )
                    continue
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
        """Run daily at 3:00 PM ET: fetch Finnhub company_news, score headlines with OpenAI."""
        logging.info("--- Job: Sentiment Refresh (Finnhub company_news + OpenAI) ---")

        if self.halted_until == date.today():
            logging.warning("Bot halted by daily loss circuit breaker — skipping sentiment refresh.")
            return

        tickers = list(self.get_active_universe().keys())
        if not tickers:
            logging.warning("Sentiment refresh: fundamental_universe is empty, skipping.")
            return

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

                    scores = []
                    for h in headlines:
                        score = _get_gpt_sentiment(h)
                        scores.append(score)
                        
                    avg_score = sum(scores) / len(scores) if scores else 0.0
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

        if self._is_paused():
            logging.info("System is paused via override. Skipping.")
            return

        if self.halted_until == date.today():
            logging.warning("Bot halted by daily loss circuit breaker — skipping order execution.")
            return

        pending = self._load_pending_orders()
        self.pending_orders = list(pending)

        if not pending:
            logging.info("No pending orders to execute.")
            return

        self.check_session_kill_switch()

        account = self.alpaca_call_with_backoff(self.trading_client.get_account)
        equity = float(account.equity)

        universe = self.get_active_universe()
        sector_exposure = self.get_sector_exposure(universe)

        bars_df = self.fetch_historical_batch(pending, lookback_days=30)

        if bars_df is None or bars_df.empty:
            logging.error("Failed to fetch historical data for order execution.")
            return

        for symbol in pending:
            ok, earnings_dates = self.fetch_earnings_calendar(symbol)
            if not ok:
                logging.warning(
                    f"{symbol}: skipped — could not verify earnings calendar (fail-closed); leaving pending"
                )
                continue  # leave in pending_orders for next attempt
            in_window, match_date = self._is_within_earnings_window(earnings_dates)
            if in_window:
                logging.info(
                    f"{symbol}: skipped — earnings within 3-day window ({match_date})"
                )
                self._delete_pending_order(symbol)
                continue

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
                    self.alpaca_call_with_backoff(self.trading_client.submit_order, order_req)
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

    def job_check_exits(self):
        """Evaluate open positions for exit signals based on regime-aware parameters."""
        logging.info("--- Job: Checking Exits ---")

        if self._is_paused():
            logging.info("System is paused via override. Skipping exits.")
            return

        if self.halted_until == date.today():
            logging.warning("Bot halted by daily loss circuit breaker — skipping exit execution.")
            return

        try:
            with self._get_conn() as conn:
                row = conn.execute("SELECT current_regime FROM portfolio_state WHERE id = 1").fetchone()
                regime = int(row[0]) if row and row[0] is not None else 2
        except Exception as e:
            logging.error(f"Failed to read current_regime: {e}")
            regime = 2

        if regime == 0:
            atr_mult = 2.5
            rsi_exit = 75
            time_stop = 7
        elif regime == 1:
            atr_mult = 1.5
            rsi_exit = 55
            time_stop = 3
        else:
            atr_mult = 3.0
            rsi_exit = 65
            time_stop = 14

        logging.info(f"Using State {regime} exit rules: ATR Mult={atr_mult}, RSI Exit={rsi_exit}, Time Stop={time_stop}")

        try:
            positions = self.alpaca_call_with_backoff(self.trading_client.get_all_positions)
        except Exception as e:
            logging.error(f"Failed to fetch positions for exit check: {e}")
            return

        if not positions:
            logging.info("No open positions to check.")
            return

        symbols = [p.symbol for p in positions]
        bars_df = self.fetch_historical_batch(symbols, lookback_days=60)

        if bars_df is None or bars_df.empty:
            logging.error("Failed to fetch historical data for exits.")
            return

        for p in positions:
            symbol = p.symbol
            try:
                df = bars_df.loc[symbol].copy()
            except KeyError:
                continue

            if len(df) < 15:
                continue

            rsi = calculate_rsi(df['close'])
            atr = calculate_atr(df['high'], df['low'], df['close'])
            current_rsi = rsi.iloc[-1]
            current_atr = atr.iloc[-1]
            current_price = df.iloc[-1]['close']

            # Estimate peak price over the holding period (using time_stop as a rough window)
            peak_price = df['high'].iloc[-time_stop:].max()

            exit_reasons = []

            # 1. RSI Overbought
            if current_rsi > rsi_exit:
                exit_reasons.append(f"RSI {current_rsi:.1f} > {rsi_exit}")

            # 3. Trailing Stop
            if (peak_price - current_price) > (atr_mult * current_atr):
                exit_reasons.append(f"Trailing stop {atr_mult}x breached (Peak: {peak_price:.2f}, Drop: {peak_price - current_price:.2f})")

            # Execute exit if any conditions met
            if exit_reasons:
                logging.info(f"Closing {symbol}. Reasons: {', '.join(exit_reasons)}")
                try:
                    self.alpaca_call_with_backoff(
                        self.trading_client.close_position,
                        symbol_or_asset_id=symbol
                    )
                except Exception as e:
                    logging.error(f"Failed to close position {symbol}: {e}")

    def run(self):
        """Infinite loop to process timezone-aware scheduling."""
        eastern = pytz.timezone('US/Eastern')
        logging.info("Starting autonomous bot execution loop...")

        executed_today = {
            'sentiment': None,
            'scan': None,
            'execute': None,
            'exits': None,
        }

        last_kill_switch_check = None

        while True:
            now_et = datetime.now(eastern)
            is_weekday = now_et.weekday() < 5
            today_str = now_et.strftime('%Y-%m-%d')

            # Day rollover: clear stale halted_until so the sidecar reports halted=false
            if self.halted_until is not None and self.halted_until != date.today():
                self.halted_until = None
                self._persist_halted_until(None)

            if is_weekday:
                # 3:00 PM ET — Sentiment refresh
                if now_et.hour == 15 and now_et.minute == 0:
                    if executed_today['sentiment'] != today_str:
                        self.job_populate_sentiment()
                        executed_today['sentiment'] = today_str

                # 3:45 PM ET — Check Exits
                if now_et.hour == 15 and now_et.minute == 45:
                    if executed_today['exits'] != today_str:
                        self.job_check_exits()
                        executed_today['exits'] = today_str

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

                # Periodic circuit-breaker + kill-switch checks during market hours (every 5 min)
                if self.check_market_hours():
                    if last_kill_switch_check is None or \
                       (now_et - last_kill_switch_check) >= timedelta(minutes=5):
                        
                        self._update_system_state()

                        if self.halted_until != date.today() and not self._is_paused():
                            try:
                                self.check_daily_loss_circuit_breaker()
                            except Exception as e:
                                logging.error(f"Daily loss circuit breaker check failed: {e}")
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
