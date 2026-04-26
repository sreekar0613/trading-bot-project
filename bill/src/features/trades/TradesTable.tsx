import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getTrades } from "@/services/api";
import { Badge } from "@/components/Badge";
import { Tooltip } from "@/components/Tooltip";
import type { TradePayload } from "@/types/api";

const PAGE_SIZE = 20;

const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

function formatDate(ts: string): string {
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return ts;
  const mo = MONTHS[d.getMonth()];
  const day = d.getDate();
  const yr = d.getFullYear();
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${mo} ${day} ${yr} ${hh}:${mm}`;
}

function formatUsd(v: number): string {
  return v.toLocaleString("en-US", { style: "currency", currency: "USD" });
}

function formatUsdSigned(v: number): string {
  const sign = v >= 0 ? "+" : "-";
  return `${sign}${Math.abs(v).toLocaleString("en-US", { style: "currency", currency: "USD" })}`;
}

export function TradesTable() {
  const { data, isLoading } = useQuery({
    queryKey: ["trades"],
    queryFn: getTrades,
    refetchInterval: 30_000,
  });

  const [page, setPage] = useState(1);

  const trades = data ?? [];
  const totalPages = Math.max(1, Math.ceil(trades.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const pageRows = useMemo(() => {
    const start = (safePage - 1) * PAGE_SIZE;
    return trades.slice(start, start + PAGE_SIZE);
  }, [trades, safePage]);

  return (
    <div className="w-full">
      <div className="w-full overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr className="border-b border-border">
              <Th align="left">Date</Th>
              <Th align="left">Symbol</Th>
              <Th align="left">Side</Th>
              <Th align="right">Qty</Th>
              <Th align="right">Price</Th>
              <Th align="right">Realized PnL</Th>
              <Th align="left">Reason</Th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <tr
                  key={i}
                  className={`h-12 border-b border-border ${i % 2 === 0 ? "bg-bg" : "bg-surface"}`}
                >
                  {Array.from({ length: 7 }).map((_, j) => (
                    <td key={j} className="px-3">
                      <div className="h-3 w-20 animate-pulse rounded bg-border" />
                    </td>
                  ))}
                </tr>
              ))
            ) : pageRows.length === 0 ? (
              <tr>
                <td colSpan={7} className="py-12 text-center">
                  <p className="font-display text-lg italic text-text-secondary">
                    No trades recorded yet.
                  </p>
                </td>
              </tr>
            ) : (
              pageRows.map((t, i) => (
                <TradeRow key={t.id} trade={t} striped={i % 2 === 0} />
              ))
            )}
          </tbody>
        </table>
      </div>

      {!isLoading && trades.length > 0 && (
        <div className="mt-4 flex items-center justify-center gap-4">
          <button
            type="button"
            disabled={safePage <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            className="h-8 rounded-input border border-border bg-surface px-3 text-xs text-text-primary transition-opacity hover:bg-bg disabled:cursor-not-allowed disabled:opacity-40"
          >
            Prev
          </button>
          <span className="text-xs tabular-nums text-text-secondary">
            Page {safePage} of {totalPages}
          </span>
          <button
            type="button"
            disabled={safePage >= totalPages}
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            className="h-8 rounded-input border border-border bg-surface px-3 text-xs text-text-primary transition-opacity hover:bg-bg disabled:cursor-not-allowed disabled:opacity-40"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}

function TradeRow({ trade, striped }: { trade: TradePayload; striped: boolean }) {
  const pnl = trade.realized_pnl ?? null;
  const pnlTone =
    pnl == null || pnl === 0
      ? "text-text-secondary"
      : pnl > 0
        ? "text-bull"
        : "text-critical";

  return (
    <tr className={`h-12 border-b border-border ${striped ? "bg-bg" : "bg-surface"}`}>
      <td className="px-3 text-left text-sm tabular-nums text-text-secondary">
        {formatDate(trade.timestamp)}
      </td>
      <td className="px-3 text-left font-mono text-sm font-semibold text-text-primary">
        {trade.symbol}
      </td>
      <td className="px-3 text-left">
        <Badge tone={trade.side === "buy" ? "bull" : "critical"}>
          {trade.side.toUpperCase()}
        </Badge>
      </td>
      <td className="px-3 text-right text-sm tabular-nums">
        {trade.qty.toLocaleString("en-US", { maximumFractionDigits: 4 })}
      </td>
      <td className="px-3 text-right text-sm tabular-nums">
        {formatUsd(trade.price)}
      </td>
      <td className={`px-3 text-right text-sm font-medium tabular-nums ${pnlTone}`}>
        {pnl == null || pnl === 0 ? "—" : formatUsdSigned(pnl)}
      </td>
      <td className="px-3 text-left">
        {trade.reason ? (
          <Tooltip content={trade.reason}>
            <span className="block max-w-[220px] truncate text-xs text-text-secondary">
              {trade.reason}
            </span>
          </Tooltip>
        ) : (
          <span className="text-xs text-text-secondary">—</span>
        )}
      </td>
    </tr>
  );
}

function Th({ children, align }: { children: React.ReactNode; align: "left" | "right" }) {
  return (
    <th
      className={`px-3 py-2 text-[11px] font-medium uppercase tracking-wide text-text-secondary ${
        align === "right" ? "text-right" : "text-left"
      }`}
    >
      {children}
    </th>
  );
}
