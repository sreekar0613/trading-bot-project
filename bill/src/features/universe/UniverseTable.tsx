import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as RToggle from "@radix-ui/react-toggle";
import { ArrowDown, ArrowUp, ArrowUpDown, Search } from "lucide-react";
import {
  blacklistTicker,
  getUniverse,
  unblacklistTicker,
} from "@/services/api";
import { Badge } from "@/components/Badge";
import { useToastStore } from "@/components/Toast";
import type { UniversePayload } from "@/types/api";

type SortKey = "symbol" | "sector" | "market_cap" | "roe" | "sentiment" | "signal" | "blacklisted";
type SortDir = "asc" | "desc";

interface SortState {
  key: SortKey;
  dir: SortDir;
}

type SignalLevel = "STRONG BUY" | "BUY" | "HOLD" | "SELL";

function deriveSignal(sentiment: number, roe: number): SignalLevel {
  if (sentiment > 0.15 && roe > 15) return "STRONG BUY";
  if (sentiment > 0 && roe > 0) return "BUY";
  if (sentiment >= -0.05) return "HOLD";
  return "SELL";
}

const SIGNAL_TONE: Record<SignalLevel, "bull" | "bear" | "warn" | "neutral" | "critical"> = {
  "STRONG BUY": "bull",
  BUY: "bull",
  HOLD: "neutral",
  SELL: "critical",
};

const SIGNAL_RANK: Record<SignalLevel, number> = {
  "STRONG BUY": 3,
  BUY: 2,
  HOLD: 1,
  SELL: 0,
};

function formatMarketCap(n: number | null): string {
  if (n == null) return "—";
  const abs = Math.abs(n);
  if (abs >= 1e12) return `$${(n / 1e12).toFixed(1)}T`;
  if (abs >= 1e9) return `$${(n / 1e9).toFixed(0)}B`;
  if (abs >= 1e6) return `$${(n / 1e6).toFixed(0)}M`;
  return `$${n.toFixed(0)}`;
}

function formatRoe(roe: number | null): string {
  if (roe == null) return "—";
  return `${roe.toFixed(1)}%`;
}

function roeTone(roe: number | null): string {
  if (roe == null) return "text-text-secondary";
  if (roe > 15) return "text-bull";
  if (roe < 0) return "text-critical";
  return "text-text-primary";
}

export function UniverseTable() {
  const queryClient = useQueryClient();
  const pushToast = useToastStore((s) => s.push);

  const { data, isLoading } = useQuery({
    queryKey: ["universe"],
    queryFn: getUniverse,
  });

  const [sort, setSort] = useState<SortState>({ key: "market_cap", dir: "desc" });
  const [activeSector, setActiveSector] = useState<string>("All");
  const [search, setSearch] = useState("");

  const sectors = useMemo(() => {
    const set = new Set<string>();
    for (const row of data ?? []) {
      if (row.sector) set.add(row.sector);
    }
    return ["All", ...Array.from(set).sort()];
  }, [data]);

  const filtered = useMemo(() => {
    const rows = data ?? [];
    const q = search.trim().toLowerCase();
    return rows.filter((r) => {
      if (activeSector !== "All" && (r.sector ?? "") !== activeSector) return false;
      if (!q) return true;
      return (
        r.symbol.toLowerCase().includes(q) ||
        (r.sector ?? "").toLowerCase().includes(q)
      );
    });
  }, [data, activeSector, search]);

  const sorted = useMemo(() => {
    const rows = [...filtered];
    const dir = sort.dir === "asc" ? 1 : -1;
    rows.sort((a, b) => {
      const av = sortValue(a, sort.key);
      const bv = sortValue(b, sort.key);
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      if (av < bv) return -1 * dir;
      if (av > bv) return 1 * dir;
      return 0;
    });
    return rows;
  }, [filtered, sort]);

  const blacklistMutation = useMutation({
    mutationFn: async (vars: { symbol: string; nextBlacklisted: boolean }) => {
      return vars.nextBlacklisted
        ? blacklistTicker(vars.symbol)
        : unblacklistTicker(vars.symbol);
    },
    onMutate: async (vars) => {
      await queryClient.cancelQueries({ queryKey: ["universe"] });
      const previous = queryClient.getQueryData<UniversePayload[]>(["universe"]);
      queryClient.setQueryData<UniversePayload[]>(["universe"], (old) =>
        (old ?? []).map((r) =>
          r.symbol === vars.symbol ? { ...r, blacklisted: vars.nextBlacklisted } : r,
        ),
      );
      return { previous };
    },
    onError: (_err, vars, ctx) => {
      if (ctx?.previous) queryClient.setQueryData(["universe"], ctx.previous);
      pushToast(`Failed to update ${vars.symbol}`, "error");
    },
    onSuccess: (_res, vars) => {
      pushToast(
        vars.nextBlacklisted ? `${vars.symbol} blacklisted` : `${vars.symbol} unblacklisted`,
        "neutral",
      );
    },
  });

  const toggleSort = (key: SortKey) => {
    setSort((prev) =>
      prev.key === key
        ? { key, dir: prev.dir === "asc" ? "desc" : "asc" }
        : { key, dir: "asc" },
    );
  };

  return (
    <div className="w-full">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          {sectors.map((s) => {
            const active = s === activeSector;
            return (
              <button
                key={s}
                type="button"
                onClick={() => setActiveSector(s)}
                className={`rounded-full border px-3 py-1 text-xs transition-colors ${
                  active
                    ? "bg-text-primary text-white border-text-primary"
                    : "border-border text-text-secondary hover:text-text-primary"
                }`}
              >
                {s}
              </button>
            );
          })}
        </div>
        <div className="relative">
          <Search
            size={14}
            className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-text-secondary"
          />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search symbol or sector"
            className="h-8 w-64 rounded-input border border-border bg-surface pl-7 pr-3 text-xs text-text-primary placeholder:text-text-secondary focus:border-text-primary focus:outline-none"
          />
        </div>
      </div>

      <div className="w-full overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr className="border-b border-border">
              <SortableTh label="Ticker" sortKey="symbol" sort={sort} onClick={toggleSort} align="left" />
              <SortableTh label="Sector" sortKey="sector" sort={sort} onClick={toggleSort} align="left" />
              <SortableTh label="Market Cap" sortKey="market_cap" sort={sort} onClick={toggleSort} align="right" />
              <SortableTh label="ROE" sortKey="roe" sort={sort} onClick={toggleSort} align="right" />
              <SortableTh label="Sentiment" sortKey="sentiment" sort={sort} onClick={toggleSort} align="left" />
              <SortableTh label="Signal" sortKey="signal" sort={sort} onClick={toggleSort} align="left" />
              <SortableTh label="Blacklisted" sortKey="blacklisted" sort={sort} onClick={toggleSort} align="right" />
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <tr key={i} className={`h-12 border-b border-border ${i % 2 === 0 ? "bg-bg" : "bg-surface"}`}>
                  {Array.from({ length: 7 }).map((_, j) => (
                    <td key={j} className="px-3">
                      <div className="h-3 w-20 animate-pulse rounded bg-border" />
                    </td>
                  ))}
                </tr>
              ))
            ) : sorted.length === 0 ? (
              <tr>
                <td colSpan={7} className="py-12 text-center">
                  <p className="font-display text-lg italic text-text-secondary">
                    No tickers match the filter.
                  </p>
                </td>
              </tr>
            ) : (
              sorted.map((row, i) => {
                const sentiment = row.sentiment_score ?? 0;
                const roe = row.roe ?? 0;
                const signal = deriveSignal(sentiment, roe);
                return (
                  <tr
                    key={row.symbol}
                    className={`h-12 border-b border-border ${i % 2 === 0 ? "bg-bg" : "bg-surface"}`}
                  >
                    <td className="px-3 text-left font-semibold text-text-primary">{row.symbol}</td>
                    <td className="px-3 text-left text-text-secondary">{row.sector ?? "—"}</td>
                    <td className="px-3 text-right tabular-nums">{formatMarketCap(row.market_cap)}</td>
                    <td className={`px-3 text-right tabular-nums font-medium ${roeTone(row.roe)}`}>
                      {formatRoe(row.roe)}
                    </td>
                    <td className="px-3">
                      <SentimentBar score={sentiment} />
                    </td>
                    <td className="px-3">
                      <Badge tone={SIGNAL_TONE[signal]}>{signal}</Badge>
                    </td>
                    <td className="px-3 text-right">
                      <RToggle.Root
                        pressed={!!row.blacklisted}
                        onPressedChange={(pressed) =>
                          blacklistMutation.mutate({ symbol: row.symbol, nextBlacklisted: pressed })
                        }
                        aria-label={`Blacklist ${row.symbol}`}
                        className="group inline-flex h-6 w-11 items-center rounded-full border border-border bg-surface transition-colors data-[state=on]:border-critical data-[state=on]:bg-critical/15"
                      >
                        <span className="ml-0.5 inline-block h-5 w-5 rounded-full bg-text-secondary transition-all group-data-[state=on]:translate-x-5 group-data-[state=on]:bg-critical" />
                      </RToggle.Root>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function sortValue(row: UniversePayload, key: SortKey): number | string | null {
  switch (key) {
    case "symbol":
      return row.symbol;
    case "sector":
      return row.sector ?? "";
    case "market_cap":
      return row.market_cap;
    case "roe":
      return row.roe;
    case "sentiment":
      return row.sentiment_score ?? null;
    case "signal":
      return SIGNAL_RANK[deriveSignal(row.sentiment_score ?? 0, row.roe ?? 0)];
    case "blacklisted":
      return row.blacklisted ? 1 : 0;
  }
}

function SortableTh({
  label,
  sortKey,
  sort,
  onClick,
  align,
}: {
  label: string;
  sortKey: SortKey;
  sort: SortState;
  onClick: (key: SortKey) => void;
  align: "left" | "right";
}) {
  const active = sort.key === sortKey;
  const Icon = !active ? ArrowUpDown : sort.dir === "asc" ? ArrowUp : ArrowDown;
  return (
    <th
      className={`px-3 py-2 text-[11px] font-medium uppercase tracking-wide text-text-secondary ${
        align === "right" ? "text-right" : "text-left"
      }`}
    >
      <button
        type="button"
        onClick={() => onClick(sortKey)}
        className={`inline-flex items-center gap-1 hover:text-text-primary ${
          active ? "text-text-primary" : ""
        }`}
      >
        <span>{label}</span>
        <Icon size={11} />
      </button>
    </th>
  );
}

function SentimentBar({ score }: { score: number }) {
  const clamped = Math.max(-1, Math.min(1, score));
  const widthPct = Math.abs(clamped) * 100;
  const tone =
    clamped > 0
      ? "bg-bull"
      : clamped < 0
        ? "bg-critical"
        : "bg-text-secondary";
  const sign = score > 0 ? "+" : "";
  return (
    <div className="flex items-center gap-2">
      <div className="relative h-1.5 w-24 overflow-hidden rounded-full bg-border">
        <div className={`h-full ${tone}`} style={{ width: `${widthPct}%` }} />
      </div>
      <span className="text-xs tabular-nums text-text-secondary">
        {sign}
        {score.toFixed(3)}
      </span>
    </div>
  );
}
