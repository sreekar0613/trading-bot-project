import { useQuery } from "@tanstack/react-query";
import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";
import { getMetrics } from "@/services/api";

const BULL = "#00C805";
const CRITICAL = "#D93025";

export function WinLossChart() {
  const { data: metrics } = useQuery({
    queryKey: ["metrics"],
    queryFn: getMetrics,
    refetchInterval: 60_000,
  });

  const winRate = metrics?.win_rate ?? 0.6;
  const lossRate = 1 - winRate;
  const winPct = Math.round(winRate * 100);
  const lossPct = 100 - winPct;

  const data = [
    { name: "Win", value: winRate },
    { name: "Loss", value: lossRate },
  ];

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="mb-3 flex items-baseline justify-between">
        <h3 className="text-sm font-medium text-text-primary">Win / Loss</h3>
      </div>
      <div className="relative" style={{ width: "100%", height: 200 }}>
        <ResponsiveContainer>
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              innerRadius={55}
              outerRadius={85}
              startAngle={90}
              endAngle={-270}
              stroke="none"
              isAnimationActive={false}
            >
              <Cell fill={BULL} />
              <Cell fill={CRITICAL} />
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <div className="text-2xl font-semibold tabular-nums text-text-primary">{winPct}%</div>
          <div className="text-xs text-text-secondary">Win Rate</div>
        </div>
      </div>
      <div className="mt-3 flex items-center justify-center gap-6 text-xs">
        <div className="flex items-center gap-2 text-text-secondary">
          <span className="inline-block h-2 w-2 rounded-full" style={{ background: BULL }} />
          <span>Wins {winPct}%</span>
        </div>
        <div className="flex items-center gap-2 text-text-secondary">
          <span className="inline-block h-2 w-2 rounded-full" style={{ background: CRITICAL }} />
          <span>Losses {lossPct}%</span>
        </div>
      </div>
    </div>
  );
}
