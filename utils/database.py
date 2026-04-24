import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "trading_bot.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_universe() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT symbol, market_cap, roe, earnings_growth, sector, last_updated "
            "FROM fundamental_universe ORDER BY symbol"
        ).fetchall()
    return [
        {
            "symbol": r["symbol"],
            "market_cap": float(r["market_cap"]) if r["market_cap"] is not None else None,
            "roe": float(r["roe"]) if r["roe"] is not None else None,
            "earnings_growth": float(r["earnings_growth"]) if r["earnings_growth"] is not None else None,
            "sector": r["sector"],
            "last_updated": r["last_updated"],
        }
        for r in rows
    ]


def get_sentiment() -> list[dict]:
    with _connect() as conn:
        # Latest record per symbol
        rows = conn.execute(
            """
            SELECT s.symbol, s.date, s.sentiment_score, s.buzz_ratio, s.articles_count
            FROM sentiment_cache s
            INNER JOIN (
                SELECT symbol, MAX(date) AS max_date FROM sentiment_cache GROUP BY symbol
            ) latest ON s.symbol = latest.symbol AND s.date = latest.max_date
            ORDER BY s.symbol
            """
        ).fetchall()
    return [
        {
            "symbol": r["symbol"],
            "date": r["date"],
            "sentiment_score": float(r["sentiment_score"]) if r["sentiment_score"] is not None else None,
            "buzz_ratio": float(r["buzz_ratio"]) if r["buzz_ratio"] is not None else None,
            "articles_count": int(r["articles_count"]) if r["articles_count"] is not None else None,
        }
        for r in rows
    ]


def get_trades(limit: int = 50) -> list[dict]:
    """Read from backtest/signals_log.csv — returns last `limit` rows."""
    import csv
    signals_path = Path(__file__).resolve().parent.parent / "backtest" / "signals_log.csv"
    if not signals_path.exists():
        return []

    with open(signals_path, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    rows = rows[-limit:]
    result = []
    for r in rows:
        result.append({
            "date": r.get("date"),
            "symbol": r.get("symbol"),
            "signal_type": r.get("signal_type"),
            "price": float(r["price"]) if r.get("price") else None,
            "atr": float(r["atr"]) if r.get("atr") else None,
            "reason": r.get("reason"),
            "days_held": int(r["days_held"]) if r.get("days_held") else None,
        })
    return result


def get_metrics() -> dict:
    """Compute performance metrics from backtest_results.csv."""
    import csv
    results_path = Path(__file__).resolve().parent.parent / "reports" / "backtest_results.csv"
    equity_path = Path(__file__).resolve().parent.parent / "reports" / "equity_curve.csv"

    if not results_path.exists():
        return {}

    with open(results_path, newline="") as f:
        trades = list(csv.DictReader(f))

    if not trades:
        return {}

    pnl_pcts = [float(t["PnL %"]) for t in trades if t.get("PnL %")]
    wins = [p for p in pnl_pcts if p > 0]
    losses = [p for p in pnl_pcts if p <= 0]

    win_rate = len(wins) / len(pnl_pcts) if pnl_pcts else 0.0
    gross_profit = sum(wins) if wins else 0.0
    gross_loss = abs(sum(losses)) if losses else 0.0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0.0

    # Max drawdown and Sharpe from equity curve
    max_drawdown = 0.0
    sharpe_ratio = 0.0
    total_return = 0.0

    if equity_path.exists():
        import numpy as np
        with open(equity_path, newline="") as f:
            eq_rows = list(csv.DictReader(f))

        drawdowns = [float(r["Drawdown"]) for r in eq_rows if r.get("Drawdown")]
        if drawdowns:
            max_drawdown = max(drawdowns)

        returns = [float(r["Return"]) for r in eq_rows if r.get("Return")]
        if len(returns) > 1:
            arr = np.array(returns)
            sharpe_ratio = float((arr.mean() / arr.std()) * (252 ** 0.5)) if arr.std() > 0 else 0.0

        equities = [float(r["Equity"]) for r in eq_rows if r.get("Equity")]
        if len(equities) >= 2:
            total_return = (equities[-1] - equities[0]) / equities[0] * 100

    return {
        "sharpe_ratio": round(sharpe_ratio, 4),
        "max_drawdown": round(max_drawdown, 4),
        "profit_factor": round(profit_factor, 4),
        "win_rate": round(win_rate, 4),
        "total_return": round(total_return, 4),
    }
