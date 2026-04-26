import NumberFlow, { type Format } from "@number-flow/react";
import { useQuery } from "@tanstack/react-query";
import { getAccount, getMetrics } from "@/services/api";

type Tone = "bull" | "bear" | "neutral" | "auto";

function toneClass(tone: Tone, value: number) {
  if (tone === "bull") return "text-bull";
  if (tone === "bear") return "text-critical";
  if (tone === "auto") return value >= 0 ? "text-bull" : "text-critical";
  return "text-text-primary";
}

interface CardProps {
  label: string;
  value: number | null | undefined;
  format: Format;
  tone?: Tone;
  prefix?: string;
}

function MetricCard({ label, value, format, tone = "neutral", prefix }: CardProps) {
  const isReady = value !== null && value !== undefined;
  const numeric = isReady ? (value as number) : 0;

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="text-[12px] uppercase tracking-wide text-text-secondary">{label}</div>
      <div
        className={`mt-2 text-[24px] font-semibold tabular-nums ${toneClass(tone, numeric)}`}
        data-numeric
      >
        {isReady ? (
          <>
            {prefix && numeric >= 0 ? prefix : ""}
            <NumberFlow value={numeric} format={format} />
          </>
        ) : (
          <span className="text-text-secondary">—</span>
        )}
      </div>
    </div>
  );
}

export function MetricsCards() {
  const { data: metrics } = useQuery({
    queryKey: ["metrics"],
    queryFn: getMetrics,
    refetchInterval: 30_000,
  });
  const { data: account } = useQuery({
    queryKey: ["account"],
    queryFn: getAccount,
    refetchInterval: 10_000,
  });

  const todayPnl =
    account && account.last_equity != null
      ? account.equity - account.last_equity
      : null;

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      <MetricCard
        label="Today's PnL"
        value={todayPnl}
        format={{ style: "currency", currency: "USD", signDisplay: "always" }}
        tone="auto"
      />
      <MetricCard
        label="Total Return"
        value={metrics?.total_return ?? null}
        format={{ style: "percent", maximumFractionDigits: 2, signDisplay: "always" }}
        tone="auto"
      />
      <MetricCard
        label="Sharpe Ratio"
        value={metrics?.sharpe_ratio ?? null}
        format={{ minimumFractionDigits: 2, maximumFractionDigits: 2 }}
      />
      <MetricCard
        label="Max Drawdown"
        value={metrics?.max_drawdown ?? null}
        format={{ style: "percent", maximumFractionDigits: 2 }}
        tone="bear"
      />
    </div>
  );
}
