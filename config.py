"""Global configuration constants for the trading bot."""

# Circuit breaker: halt bot if net daily PnL falls below -4% of portfolio value.
MAX_DAILY_LOSS_PCT = 0.04

# Alpaca API retry/backoff configuration.
API_MAX_RETRIES = 5
API_BACKOFF_BASE = 2
