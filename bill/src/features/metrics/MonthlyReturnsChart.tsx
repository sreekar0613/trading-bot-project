import { useMemo } from "react";
import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

// TODO: replace with /api/metrics/monthly when endpoint ships.
function buildMockMonthly() {
  const out: { label: string; ret: number }[] = [];
  const now = new Date();
  // Seeded pseudo-random for stability across renders.
  let seed = 1337;
  const rand = () => {
    seed = (seed * 9301 + 49297) % 233280;
    return seed / 233280;
  };
  const months = 24;
  for (let i = months - 1; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    const label = `${d.toLocaleString("en-US", { month: "short" })} ${String(d.getFullYear()).slice(-2)}`;
    const ret = +(rand() * 16 - 8).toFixed(2); // ±8%
    out.push({ label, ret });
  }
  return out;
}

const BULL = "#00C805";
const CRITICAL = "#D93025";

function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { value: number }[];
  label?: string;
}) {
  if (!active || !payload || payload.length === 0) return null;
  const v = payload[0]?.value ?? 0;
  return (
    <div className="rounded-md border border-border bg-surface px-2.5 py-1.5 text-xs text-text-primary shadow-md">
      <div className="text-text-secondary">{label}</div>
      <div className={`tabular-nums ${v >= 0 ? "text-bull" : "text-critical"}`}>
        {v >= 0 ? "+" : ""}
        {v.toFixed(2)}%
      </div>
    </div>
  );
}

export function MonthlyReturnsChart() {
  const data = useMemo(buildMockMonthly, []);

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="mb-3 flex items-baseline justify-between">
        <h3 className="text-sm font-medium text-text-primary">Monthly Returns</h3>
        <span className="text-xs text-text-secondary">24m · mock data</span>
      </div>
      <div style={{ width: "100%", height: 240 }}>
        <ResponsiveContainer>
          <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <XAxis
              dataKey="label"
              tick={{ fill: "#737373", fontSize: 10 }}
              tickLine={false}
              axisLine={false}
              interval={2}
            />
            <YAxis
              tick={{ fill: "#737373", fontSize: 10 }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v) => `${v}%`}
              width={36}
            />
            <Tooltip cursor={{ fill: "rgba(115,115,115,0.08)" }} content={<CustomTooltip />} />
            <Bar dataKey="ret" radius={[2, 2, 0, 0]}>
              {data.map((d, i) => (
                <Cell key={i} fill={d.ret >= 0 ? BULL : CRITICAL} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
