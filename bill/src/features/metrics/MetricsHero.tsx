import { useQuery } from "@tanstack/react-query";
import { getMetrics } from "@/services/api";

type Tone = "auto" | "neutral" | "bear";

interface StatProps {
  label: string;
  value: number | null | undefined;
  format: (v: number) => string;
  tone?: Tone;
}

function toneClass(tone: Tone, v: number) {
  if (tone === "auto") return v >= 0 ? "text-bull" : "text-critical";
  if (tone === "bear") return "text-critical";
  return "text-text-primary";
}

function Stat({ label, value, format, tone = "neutral" }: StatProps) {
  const ready = value !== null && value !== undefined;
  const numeric = ready ? (value as number) : 0;
  return (
    <div className="flex flex-col gap-1">
      <div
        className={`font-display text-4xl tabular-nums ${ready ? toneClass(tone, numeric) : "text-text-secondary"}`}
      >
        {ready ? format(numeric) : "—"}
      </div>
      <div className="text-xs uppercase tracking-wide text-text-secondary">{label}</div>
    </div>
  );
}

const fmtPct = (v: number) =>
  `${v >= 0 ? "+" : ""}${(v * 100).toFixed(2)}%`;
const fmtPctNeg = (v: number) => `${(v * 100).toFixed(2)}%`;
const fmtRatio = (v: number) => v.toFixed(2);

export function MetricsHero() {
  const { data: metrics } = useQuery({
    queryKey: ["metrics"],
    queryFn: getMetrics,
    refetchInterval: 60_000,
  });

  return (
    <div className="grid grid-cols-2 gap-6 rounded-lg border border-border bg-surface p-6 lg:grid-cols-4">
      <Stat
        label="Total Return"
        value={metrics?.total_return ?? null}
        format={fmtPct}
        tone="auto"
      />
      <Stat
        label="Sharpe Ratio"
        value={metrics?.sharpe_ratio ?? null}
        format={fmtRatio}
      />
      <Stat
        label="Max Drawdown"
        value={metrics?.max_drawdown ?? null}
        format={fmtPctNeg}
        tone="bear"
      />
      <Stat
        label="Profit Factor"
        value={metrics?.profit_factor ?? null}
        format={fmtRatio}
      />
    </div>
  );
}
