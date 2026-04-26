import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { getTrades } from "@/services/api";
import { Button } from "@/components/Button";
import type { TradePayload } from "@/types/api";

const CSV_HEADERS = ["Date", "Symbol", "Side", "Qty", "Price", "Realized PnL", "Reason"];

function escapeCsv(value: string | number | null | undefined): string {
  if (value == null) return "";
  const s = String(value);
  if (/[",\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

function buildCsv(trades: TradePayload[]): string {
  const rows = [CSV_HEADERS.join(",")];
  for (const t of trades) {
    rows.push(
      [
        escapeCsv(t.timestamp),
        escapeCsv(t.symbol),
        escapeCsv(t.side.toUpperCase()),
        escapeCsv(t.qty),
        escapeCsv(t.price),
        escapeCsv(t.realized_pnl ?? ""),
        escapeCsv(t.reason ?? ""),
      ].join(","),
    );
  }
  return rows.join("\n");
}

function todayStamp(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function CSVExport() {
  const { data } = useQuery({
    queryKey: ["trades"],
    queryFn: getTrades,
  });

  const handleExport = () => {
    const trades = data ?? [];
    const csv = buildCsv(trades);
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `bill-trades-${todayStamp()}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <Button variant="secondary" size="sm" onClick={handleExport} disabled={!data}>
      <Download size={14} />
      Export CSV
    </Button>
  );
}
