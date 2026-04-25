"""Walk-forward + Monte Carlo validation on backtest results."""
from __future__ import annotations

import argparse
import io
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

REPO = Path(__file__).resolve().parent


def _paths(variant: str | None):
    suffix = f"_{variant}" if variant else ""
    return (
        REPO / "reports" / f"backtest_results{suffix}.csv",
        REPO / "reports" / f"equity_curve{suffix}.csv",
        REPO / "reports" / f"validation_report{suffix}.txt",
    )


TRADES_CSV, EQUITY_CSV, REPORT_TXT = _paths(None)

STARTING_EQUITY = 1100.0
RUIN_THRESHOLD = 770.0
RF_ANNUAL = 0.045
TRADING_DAYS = 252
MC_RUNS = 10_000
RNG_SEED = 42


def annualised_return(daily_returns: pd.Series) -> float:
    if len(daily_returns) == 0:
        return 0.0
    total = (1 + daily_returns).prod()
    years = len(daily_returns) / TRADING_DAYS
    if years <= 0 or total <= 0:
        return 0.0
    return total ** (1 / years) - 1


def sharpe(daily_returns: pd.Series) -> float:
    excess = daily_returns - RF_ANNUAL / TRADING_DAYS
    sd = excess.std(ddof=1)
    if sd == 0 or np.isnan(sd):
        return 0.0
    return float(np.sqrt(TRADING_DAYS) * excess.mean() / sd)


def sortino(daily_returns: pd.Series) -> float:
    excess = daily_returns - RF_ANNUAL / TRADING_DAYS
    downside = excess[excess < 0]
    dd = downside.std(ddof=1)
    if dd == 0 or np.isnan(dd) or len(downside) < 2:
        return 0.0
    return float(np.sqrt(TRADING_DAYS) * excess.mean() / dd)


def max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    dd = (equity - peak) / peak
    return float(dd.min())


def calmar(daily_returns: pd.Series, equity: pd.Series) -> float:
    mdd = abs(max_drawdown(equity))
    if mdd == 0:
        return 0.0
    return annualised_return(daily_returns) / mdd


def deflated_sharpe(daily_returns: pd.Series) -> float:
    """Lopez de Prado's DSR (per-period SR, benchmark = 0)."""
    r = daily_returns.dropna()
    if len(r) < 3:
        return 0.0
    sr_hat = r.mean() / r.std(ddof=1)
    skew = float(stats.skew(r, bias=False))
    kurt = float(stats.kurtosis(r, bias=False, fisher=False))  # non-excess
    T = len(r)
    denom = np.sqrt(1 - skew * sr_hat + ((kurt - 1) / 4) * sr_hat ** 2)
    if denom == 0 or np.isnan(denom):
        return 0.0
    z = sr_hat * np.sqrt(T - 1) / denom
    return float(stats.norm.cdf(z))


def window_metrics(trades: pd.DataFrame) -> dict:
    if len(trades) == 0:
        return {"n": 0, "win_rate": np.nan, "avg_pnl_pct": np.nan,
                "profit_factor": np.nan, "ann_return": np.nan}
    wins = trades[trades["PnL $"] > 0]["PnL $"].sum()
    losses = -trades[trades["PnL $"] < 0]["PnL $"].sum()
    pf = (wins / losses) if losses > 0 else np.inf
    win_rate = (trades["PnL $"] > 0).mean()
    avg_pnl = trades["PnL %"].mean()
    # rough annualised return: chain pnl% over window span
    growth = (1 + trades["PnL %"] / 100.0).prod()
    span_days = (trades["Exit Date"].max() - trades["Entry Date"].min()).days
    years = max(span_days / 365.25, 1e-6)
    ann = growth ** (1 / years) - 1 if growth > 0 else -1.0
    return {"n": len(trades), "win_rate": win_rate, "avg_pnl_pct": avg_pnl,
            "profit_factor": pf, "ann_return": ann}


def monte_carlo(pnl_dollars: np.ndarray, n_runs: int = MC_RUNS) -> dict:
    rng = np.random.default_rng(RNG_SEED)
    n_trades = len(pnl_dollars)
    finals = np.empty(n_runs)
    mdds = np.empty(n_runs)
    ruined = 0
    for i in range(n_runs):
        sample = rng.choice(pnl_dollars, size=n_trades, replace=True)
        equity = STARTING_EQUITY + np.cumsum(sample)
        equity = np.concatenate(([STARTING_EQUITY], equity))
        finals[i] = equity[-1]
        peak = np.maximum.accumulate(equity)
        dd = (equity - peak) / peak
        mdds[i] = dd.min()
        if equity.min() < RUIN_THRESHOLD:
            ruined += 1
    return {
        "final_p5": float(np.percentile(finals, 5)),
        "final_p50": float(np.median(finals)),
        "final_p95": float(np.percentile(finals, 95)),
        "mdd_p5": float(np.percentile(mdds, 5)),
        "mdd_p50": float(np.median(mdds)),
        "mdd_p95": float(np.percentile(mdds, 95)),
        "risk_of_ruin": ruined / n_runs,
    }


def main() -> None:
    global TRADES_CSV, EQUITY_CSV, REPORT_TXT
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", default=None,
                        help="Optional CSV suffix, e.g. 'relaxed'")
    args = parser.parse_args()
    TRADES_CSV, EQUITY_CSV, REPORT_TXT = _paths(args.variant)

    buf = io.StringIO()

    def out(line: str = "") -> None:
        print(line)
        buf.write(line + "\n")

    trades = pd.read_csv(TRADES_CSV, parse_dates=["Entry Date", "Exit Date"])
    equity = pd.read_csv(EQUITY_CSV, parse_dates=["Date"])
    daily_ret = equity["Return"].dropna()

    out("=" * 70)
    out("STRATEGY VALIDATION REPORT")
    out("=" * 70)
    out(f"Trades: {len(trades)}   Equity series: {len(equity)} days")
    out("")

    # 1. Statistical significance
    out("1. STATISTICAL SIGNIFICANCE (one-sample t-test, H0: mean PnL% = 0)")
    out("-" * 70)
    t_stat, p_val = stats.ttest_1samp(trades["PnL %"], 0.0)
    out(f"  n trades       : {len(trades)}")
    out(f"  mean PnL %     : {trades['PnL %'].mean():.4f}")
    out(f"  std  PnL %     : {trades['PnL %'].std(ddof=1):.4f}")
    out(f"  t-statistic    : {t_stat:.4f}")
    out(f"  p-value        : {p_val:.4f}")
    significant = p_val < 0.05
    out(f"  significant @5%: {significant}")
    if len(trades) < 200:
        out(f"  WARNING: n={len(trades)} < 200 — institutionally insufficient sample.")
    out("")

    # 2. Core metrics
    out("2. CORE PERFORMANCE METRICS (from daily equity curve)")
    out("-" * 70)
    sr = sharpe(daily_ret)
    so = sortino(daily_ret)
    cal = calmar(daily_ret, equity["Equity"])
    dsr = deflated_sharpe(daily_ret)
    ann = annualised_return(daily_ret)
    mdd = max_drawdown(equity["Equity"])
    out(f"  Annualised return : {ann*100:.2f}%")
    out(f"  Max drawdown      : {mdd*100:.2f}%")
    out(f"  Sharpe (rf=4.5%)  : {sr:.4f}")
    out(f"  Sortino           : {so:.4f}")
    out(f"  Calmar            : {cal:.4f}")
    out(f"  Deflated Sharpe   : {dsr:.4f}  (CDF; closer to 1 = more confident)")
    out("")

    # 3. Walk-forward
    out("3. WALK-FORWARD ANALYSIS")
    out("-" * 70)
    windows = [
        ("W1", ("2020-01-01", "2024-06-30"), ("2024-07-01", "2024-12-31")),
        ("W2", ("2020-01-01", "2023-12-31"), ("2024-01-01", "2024-12-31")),
        ("W3", ("2021-01-01", "2023-12-31"), ("2024-01-01", "2024-12-31")),
    ]
    wfes = []
    for name, (is_s, is_e), (oos_s, oos_e) in windows:
        is_mask = (trades["Entry Date"] >= is_s) & (trades["Entry Date"] <= is_e)
        oos_mask = (trades["Entry Date"] >= oos_s) & (trades["Entry Date"] <= oos_e)
        is_m = window_metrics(trades[is_mask])
        oos_m = window_metrics(trades[oos_mask])
        wfe = (oos_m["ann_return"] / is_m["ann_return"]
               if is_m["ann_return"] not in (0, np.nan) and is_m["ann_return"] > 0
               else np.nan)
        wfes.append(wfe)
        out(f"  {name}  IS {is_s}..{is_e}   OOS {oos_s}..{oos_e}")
        out(f"    IS : n={is_m['n']:>3}  win={is_m['win_rate']:.2%}  "
            f"avg={is_m['avg_pnl_pct']:.2f}%  PF={is_m['profit_factor']:.2f}  "
            f"ann={is_m['ann_return']*100:.2f}%")
        out(f"    OOS: n={oos_m['n']:>3}  win={oos_m['win_rate']:.2%}  "
            f"avg={oos_m['avg_pnl_pct']:.2f}%  PF={oos_m['profit_factor']:.2f}  "
            f"ann={oos_m['ann_return']*100:.2f}%")
        out(f"    WFE (OOS/IS ann return): {wfe:.3f}" if not np.isnan(wfe)
            else "    WFE: n/a")
        if not np.isnan(wfe) and wfe < 0.5:
            out(f"    WARNING: WFE < 0.5 — parameter instability suspected.")
        out("")
    valid_wfes = [w for w in wfes if not np.isnan(w)]
    avg_wfe = np.mean(valid_wfes) if valid_wfes else np.nan
    out(f"  Average WFE across windows: {avg_wfe:.3f}"
        if not np.isnan(avg_wfe) else "  Average WFE: n/a")
    out("")

    # 4. Monte Carlo
    out("4. MONTE CARLO SIMULATION (10,000 bootstrap runs)")
    out("-" * 70)
    mc = monte_carlo(trades["PnL $"].to_numpy())
    out(f"  Starting equity : ${STARTING_EQUITY:.2f}")
    out(f"  Trades per run  : {len(trades)}  (resampled with replacement)")
    out("")
    out("  Final equity distribution:")
    out(f"     5th  pct : ${mc['final_p5']:>9.2f}")
    out(f"    50th  pct : ${mc['final_p50']:>9.2f}")
    out(f"    95th  pct : ${mc['final_p95']:>9.2f}")
    out("")
    out("  Max drawdown distribution:")
    out(f"     5th  pct : {mc['mdd_p5']*100:>7.2f}%")
    out(f"    50th  pct : {mc['mdd_p50']*100:>7.2f}%")
    out(f"    95th  pct : {mc['mdd_p95']*100:>7.2f}%")
    out("")
    out(f"  Risk of ruin (equity < ${RUIN_THRESHOLD:.0f}): "
        f"{mc['risk_of_ruin']*100:.2f}%")
    out("")

    # 5. Verdict
    out("5. VERDICT")
    out("-" * 70)
    cond_go = mc["risk_of_ruin"] < 0.20 and sr > 0.8
    full_go = (p_val < 0.05 and sr > 1.0 and mc["risk_of_ruin"] < 0.10
               and (not np.isnan(avg_wfe)) and avg_wfe > 0.5)
    if full_go:
        verdict = "GO"
    elif cond_go:
        verdict = "CONDITIONAL GO (reduce position sizing)"
    else:
        verdict = "NO-GO"
    out(f"  Criteria checked:")
    out(f"    p-value < 0.05         : {p_val < 0.05}  ({p_val:.4f})")
    out(f"    Sharpe > 1.0           : {sr > 1.0}  ({sr:.3f})")
    out(f"    Risk of ruin < 10%     : {mc['risk_of_ruin'] < 0.10}  "
        f"({mc['risk_of_ruin']*100:.2f}%)")
    out(f"    Avg WFE > 0.5          : "
        f"{(not np.isnan(avg_wfe)) and avg_wfe > 0.5}  "
        f"({avg_wfe if not np.isnan(avg_wfe) else float('nan'):.3f})")
    out("")
    out(f"  >>> VERDICT: {verdict} <<<")
    out("=" * 70)

    REPORT_TXT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_TXT.write_text(buf.getvalue())
    print(f"\nReport saved to: {REPORT_TXT}")


if __name__ == "__main__":
    main()
