# Automated Trading Bot - Gemini AI Context

## Project Overview
This project is a fully autonomous trading system built in Python 3.11+. It uses a multi-factor analysis approach combining technical indicators, fundamental data, and news sentiment, coupled with adaptive risk management.

- **Goal:** 8–15% annual return with a medium-risk profile.
- **Tech Stack:** Python 3.11+, SQLite for local caching.
- **APIs:** 
  - **Alpaca:** Broker for order execution and historical market data.
  - **Finnhub:** News sentiment analysis.
  - **Alpha Vantage:** Fundamental data (market cap, ROE, P/B ratios).
- **Core Strategy:** Fundamental gatekeeping, technical entry signals (EMA, RSI, MACD, Bollinger Bands), volatility-adjusted position sizing, and ATR trailing stops with multi-level kill switches.

## Project Structure & Architecture
The project is organized into modular phases and directories:
- **`data/`**: Data fetching scripts for historical prices, fundamentals, and sentiment.
- **`strategy/`**: Trading logic, technical indicators, entry/exit signals, and position sizing.
- **`risk/`**: Risk management logic (stop loss, kill switches, sector limits).
- **`backtesting/`**: Validation engine using `backtrader` or `vectorbt`.
- **`live/`**: Production deployment scripts (bot event loop, monitor, alerts).
- **`.claude/CLAUDE.md`**: Master project brief containing deep strategic insights and rules.

## Setup & Configuration
1. **Environment:** Python 3.11+ using a virtual environment (`venv`).
2. **Dependencies:** Install via `pip install -r requirements.txt`. 
   - *Note:* `ta-lib` requires C dependencies. If installation fails, use `pandas-ta` as a fallback.
3. **Environment Variables:** Must be defined in a `.env` file (which is gitignored). Never hardcode API keys.
   ```bash
   ALPACA_API_KEY=your_paper_key
   ALPACA_SECRET_KEY=your_paper_secret
   ALPACA_BASE_URL=https://paper-api.alpaca.markets
   FINNHUB_API_KEY=your_finnhub_key
   ALPHA_VANTAGE_API_KEY=your_alpha_vantage_key
   ```
4. **Database Initialization:** Run `python init_database.py` to set up the local SQLite database (`trading_bot.db`).
5. **Git Hooks:** Run `cp .git-hooks/pre-commit .git/hooks/pre-commit` and `chmod +x .git/hooks/pre-commit` to prevent accidental API key commits.

## Building and Running (Phase 1)
Current focus is on Phase 1 (Data Pipeline). The following scripts are used to validate and run the pipeline:
- **Test Connections:** `python test_setup.py`
- **Fetch Historical Data:** `python fetch_historical_data.py`
- **Fetch Fundamentals:** `python fetch_fundamentals.py`
- **Generate Report:** `python generate_universe_report.py`

## Development Conventions & Guidelines
- **Security First:** Never commit `.env` files, `.db` files, or hardcode API keys. Ensure pre-commit hooks are active.
- **Milestone Guardrail (MANDATORY):** After completing any major milestone (e.g., finishing a phase, successful API integration, or critical bug fix), the agent MUST stop and prompt the user to commit changes. Do not proceed until confirmed.
- **Validation:** Always validate API responses and handle rate limits gracefully (e.g., Alpha Vantage has a strict 25 calls/day limit on the free tier).
- **Iterative Development:** The project is built in 4 phases (Data Pipeline -> Backtesting -> Paper Trading -> Live Deployment). Always refer to the corresponding `PHASE_X_PLAN.md` for current objectives.
- **Coding Style:** Follow PEP 8 guidelines. Use type hints, explicit naming, and handle exceptions (especially network/API requests) cleanly.

## Key Files to Reference
- `PROJECT_STRUCTURE.md`: Full view of the generated and expected files.
- `SETUP_GUIDE.md`: Troubleshooting and environment setup.
- `.claude/CLAUDE.md`: The definitive guide for the trading strategy and strict rules.