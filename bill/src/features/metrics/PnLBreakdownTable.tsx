import { useQuery } from "@tanstack/react-query";
import { getMetrics } from "@/services/api";

const fmtCurrency = (v: number | null) =>
  v == null
    ? "—"
    : `${v < 0 ? "-" : ""}$${Math.abs(v).toLocaleString("en-US", { maximumFractionDigits: 2 })}`;
const fmtPct = (v: number | null) => (v == null ? "—" : `${(v * 100).toFixed(2)}%`);
const fmtRatio = (v: number | null) => (v == null ? "—" : v.toFixed(2));

export function PnLBreakdownTable() {
  const { data: metrics } = useQuery({
    queryKey: ["metrics"],
    queryFn: getMetrics,
    refetchInterval: 60_000,
  });

  // TODO: replace these derivations with a real /api/metrics/pnl-breakdown endpoint.
  const totalReturn = metrics?.total_return ?? null;
  const winRate = metrics?.win_rate ?? null;
  const profitFactor = metrics?.profit_factor ?? null;
  const recoveryFactor = metrics?.recovery_factor ?? null;

  const baseCapital = 1100;
  const netPnl = totalReturn != null ? baseCapital * totalReturn : null;
  const grossProfit =
    profitFactor != null && netPnl != null
      ? (netPnl * profitFactor) / Math.max(profitFactor - 1, 0.01)
      : null;
  const grossLoss = grossProfit != null && netPnl != null ? grossProfit - netPnl : null;
  const avgWinner =
    grossProfit != null && winRate != null && winRate > 0
      ? grossProfit / Math.max(winRate * 100, 1)
      : null;
  const avgLoser =
    grossLoss != null && winRate != null && winRate < 1
      ? -grossLoss / Math.max((1 - winRate) * 100, 1)
      : null;

  const rows: { label: string; value: string }[] = [
    { label: "Gross Profit", value: fmtCurrency(grossProfit) },
    { label: "Gross Loss", value: fmtCurrency(grossLoss != null ? -grossLoss : null) },
    { label: "Net PnL", value: fmtCurrency(netPnl) },
    { label: "Profit Factor", value: fmtRatio(profitFactor) },
    { label: "Recovery Factor", value: fmtRatio(recoveryFactor) },
    { label: "Win Rate", value: fmtPct(winRate) },
    { label: "Avg Winner", value: fmtCurrency(avgWinner) },
    { label: "Avg Loser", value: fmtCurrency(avgLoser) },
  ];

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-surface">
      <div className="border-b border-border px-4 py-3">
        <h3 className="text-sm font-medium text-text-primary">PnL Breakdown</h3>
      </div>
      <table className="w-full border-collapse">
        <thead>
          <tr className="border-b border-border">
            <th className="px-4 py-2 text-left text-[11px] font-medium uppercase tracking-wide text-text-secondary">
              Metric
            </th>
            <th className="px-4 py-2 text-right text-[11px] font-medium uppercase tracking-wide text-text-secondary">
              Value
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr
              key={r.label}
              className={`border-b border-border last:border-b-0 ${i % 2 === 0 ? "bg-bg" : "bg-surface"}`}
            >
              <td className="px-4 py-2.5 text-sm text-text-primary">{r.label}</td>
              <td className="px-4 py-2.5 text-right text-sm tabular-nums text-text-primary">
                {r.value}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
