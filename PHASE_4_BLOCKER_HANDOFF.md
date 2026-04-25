# Phase 4 Blocker Handoff

> Drop this file in front of a fresh AI assistant (Claude Code). It should be able to pick up exactly where this session left off without re-deriving project state.

---

## 1. Project Overview

**What it is.** A fully autonomous, medium-risk/medium-growth equities trading bot. Multi-factor confluence model (trend + RSI oversold + MACD cross + lower Bollinger), ATR-based position sizing and trailing stop, multi-tier kill switches, daily signal scan at 4:05 PM ET, order execution next day at 10:15 AM ET. Target: 8–15% annual return on $1,100 starting capital.

**Stack.**
- Python 3.13 (venv at `./venv`)
- Broker: Alpaca (paper trading, IEX free feed)
- Data: Alpaca (OHLCV), Finnhub (sentiment + earnings calendar), Alpha Vantage (fundamentals)
- Storage: SQLite (`trading_bot.db`)
- Live runtime: systemd services on a DigitalOcean droplet
- iMessage sidecar (Bun + TypeScript) for daily summaries and Q&A
- Dashboard: FastAPI + static HTML at port 8000

**Status:** **BACKEND BLOCKED / CRASH LOOP**. Phase 4 live deployment is blocked.

---

## 2. The Problem: Dependency Deadlock

The backend is currently trapped in a deployment/startup failure loop caused by a complex dependency matrix issue regarding technical indicator libraries on Python 3.12/3.13.

- **Initial state:** We used `ta-lib`, which requires C-extensions. Compilation fails on the target deployment environment.
- **First pivot:** Attempted to use `pandas-ta` as a pure-Python fallback. However, `pandas-ta==0.3.14b` lacks a matching distribution, and `0.4.71b0` triggers a catastrophic `numba` dependency crash and a `KeyError` on internal `BBL` indexing when resolving against `pandas==2.2.1` and the locked `numpy<2` version.
- **Second pivot:** We are migrating to the `ta` library (`ta==0.11.0`), which is pure-Python and does not require a C-compiler.

---

## 3. The Environment Error

On top of the dependency crash loop, testing the `live/bot.py` script on the DigitalOcean droplet revealed an environment error:

- **Issue:** The newly implemented OpenAI `gpt-4o-mini` sentiment analyzer (Task #8) expects `OPENAI_API_KEY` to be present.
- **Symptom:** The live bot crashes or logs `CRITICAL` errors upon startup because `OPENAI_API_KEY` is not being properly loaded or is missing from the `.env` file on the droplet.

---

## 4. Technical Debt: `indicators/technical.py`

The transition from `ta-lib`/`pandas-ta` to the `ta` library has left the codebase in a partially refactored state.

- **Current state:** `indicators/technical.py` has been updated to `import ta` (specifically `from ta.momentum import RSIIndicator`, `from ta.trend import MACD, EMAIndicator`, `from ta.volatility import BollingerBands, AverageTrueRange`).
- **Debt:** While the wrapper functions `calculate_rsi`, `calculate_macd`, `calculate_bollinger`, `calculate_ema`, and `calculate_atr` have been rewritten, the integration must be rigorously verified to ensure the returned objects (DataFrames/Series) perfectly match the structural expectations (column names, index alignments, NaN padding) of `backtest/signal_generator_relaxed.py` and `live/bot.py`. Any misalignment will silently break signal generation.

---

## 5. Pending UI Tasks (Post-Unblock)

Once the backend crash loop is resolved, the dependency matrix is stable, and the live bot executes without CRITICAL errors, the following UI tasks must be completed to finalize the dashboard:

1. **Backend Endpoint:** Build the FastAPI `GET /api/history/{symbol}` endpoint in `main.py` to serve historical OHLCV data from the SQLite `price_history` table.
2. **Frontend Integration:** Integrate TradingView Lightweight Charts into the React frontend (`app.jsx`). The charts should fetch data from the new `/api/history/{symbol}` endpoint to render interactive price graphs on the dashboard.

---

## 6. Required Actions for Claude Code

1. **Verify Dependency Resolution:** Ensure `requirements.txt` strictly locks `ta==0.11.0` and `numpy>=1.26.4,<2.0.0` and that no remnants of `pandas-ta` or `ta-lib` exist.
2. **Resolve Environment Key:** Guide the user to inject `OPENAI_API_KEY` into the droplet's `.env` file and restart the `trading-bot` systemd service.
3. **Audit Technical Indicators:** Verify that the output of the refactored functions in `indicators/technical.py` is structurally identical to the legacy `ta-lib` outputs.
4. **Execute UI Tasks:** Implement the `/api/history/{symbol}` endpoint and wire up the TradingView Lightweight Charts in `app.jsx`.
5. **Address Additional Gaps:** Fix the risk mismatch, absolute path resolution in `regime.py`, ignore `.pkl` files, expose `current_regime` via API, and resolve pending order technical debt (detailed below).

---

## 7. Additional Codebase Findings / Gaps to Address

1. **Risk Mismatch (Code vs. Docs):**
   - *Issue:* The `SESSION_HANDOFF_2026_04_25.md` document strictly mandates that position sizing should be reduced to **1.5%** for the first 4 weeks of Phase 4 deployment. However, `live/bot.py` still hardcodes `self.risk_per_trade = 0.025` (2.5%). 

2. **Path Resolution & `__init__.py` in `strategy/regime.py`:**
   - *Issue:* `strategy/regime.py` defines `model_path="regime_model.pkl"`. This relies on the Current Working Directory (CWD). Depending on how the script is executed (`python live/bot.py` vs `python backtest/...`), the `.pkl` file will fracture across different folders. It should use `REPO_ROOT` like `DB_PATH`. Additionally, `strategy/` lacks an `__init__.py` file, which can break absolute module resolution for testing.

3. **Un-ignored Binary Models (`.gitignore`):**
   - *Issue:* The `.gitignore` file does not contain `*.pkl`. Once the HMM model trains and saves the `regime_model.pkl` to disk, it will accidentally be tracked by git, bloating the repository.

4. **Incomplete API Exposure of `current_regime`:**
   - *Issue:* We successfully injected the `current_regime` column into the `portfolio_state` SQLite table in `live/bot.py`. However, `main.py`'s `_bot_status()` helper does not extract or return `current_regime`. Therefore, the frontend dashboard and the iMessage Sidecar have no visibility into whether the bot is currently in the Bull, Bear, or Sideways HMM state.

5. **Lingering Technical Debt (Pending Orders):**
   - *Issue:* `SESSION_HANDOFF_2026_04_25.md` explicitly calls out: *"Pending orders have no max age... open orders can sit indefinitely if never filled or cancelled."* This structural flaw in `live/bot.py` remains unresolved.