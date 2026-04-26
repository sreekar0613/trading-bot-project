import NumberFlow from "@number-flow/react";
import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import { getPositions } from "@/services/api";
import { usePositionStore } from "@/store/positionStore";
import type { PositionPayload } from "@/types/api";

const usd = { style: "currency", currency: "USD" } as const;

export function TopPositionsWidget() {
  const { data, isLoading } = useQuery({
    queryKey: ["positions"],
    queryFn: getPositions,
    refetchInterval: 15_000,
  });

  // Prefer live WS-pushed positions when available; fall back to query data.
  const wsBySymbol = usePositionStore((s) => s.bySymbol);
  const merged: PositionPayload[] = (data ?? []).map((p) => wsBySymbol[p.symbol] ?? p);

  const top5 = [...merged]
    .sort((a, b) => Math.abs(b.unrealized_pl) - Math.abs(a.unrealized_pl))
    .slice(0, 5);

  return (
    <div className="rounded-lg border border-border bg-surface">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <h3 className="text-sm font-medium text-text-primary">Top 5 Open Positions</h3>
        <span className="text-xs text-text-secondary">By |PnL|</span>
      </div>

      <div className="divide-y divide-border">
        {isLoading && (
          <div className="px-4 py-6 text-center text-sm text-text-secondary">Loading…</div>
        )}
        {!isLoading && top5.length === 0 && (
          <div className="px-4 py-6 text-center text-sm text-text-secondary">No open positions</div>
        )}
        {top5.map((p) => {
          const positive = p.unrealized_pl >= 0;
          return (
            <div key={p.symbol} className="flex items-center justify-between px-4 py-3">
              <div className="min-w-0">
                <div className="font-semibold text-text-primary">{p.symbol}</div>
                <div className="text-xs text-text-secondary tabular-nums">
                  Entry{" "}
                  <NumberFlow value={p.avg_entry_price} format={usd} />
                </div>
              </div>
              <div
                className={`text-right font-semibold tabular-nums ${
                  positive ? "text-bull" : "text-critical"
                }`}
                data-numeric
              >
                <NumberFlow
                  value={p.unrealized_pl}
                  format={{ ...usd, signDisplay: "always" }}
                />
                <div className="text-xs font-normal">
                  <NumberFlow
                    value={p.unrealized_plpc}
                    format={{ style: "percent", maximumFractionDigits: 2, signDisplay: "always" }}
                  />
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <Link
        to="/positions"
        className="flex items-center justify-end gap-1 border-t border-border px-4 py-3 text-xs text-text-secondary hover:text-text-primary"
      >
        View all <ArrowRight size={12} />
      </Link>
    </div>
  );
}
