"""Global configuration constants for the trading bot."""

# Circuit breaker: halt bot if net daily PnL falls below -4% of portfolio value.
MAX_DAILY_LOSS_PCT = 0.04

# Alpaca API retry/backoff configuration.
API_MAX_RETRIES = 5
API_BACKOFF_BASE = 2

# Earnings exclusion: block entries if earnings fall within today-1 .. today+N days.
EARNINGS_WINDOW_DAYS = 3

# RSI oversold context threshold (relaxed from 35 to 40 per Task #5 validation)
RSI_OVERSOLD_THRESHOLD = 40

# Macro circuit breaker thresholds (Task #6)
VIX_THRESHOLD = 25
SPY_TREND_LOOKBACK = 200

# Phase 4: 1.5% risk/trade for first 4 weeks (reduced from 2.5% per Task #5)
RISK_PER_TRADE = 0.015

