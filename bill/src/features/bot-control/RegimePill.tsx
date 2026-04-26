import { useQuery } from "@tanstack/react-query";
import { getBotStatus } from "@/services/api";

type RegimeKey = "0" | "1" | "2";

const REGIME: Record<RegimeKey, { label: string; className: string }> = {
  "0": {
    label: "Low-Vol Bull",
    className: "bg-bull/10 text-bull border-bull/30",
  },
  "1": {
    label: "High-Vol Bear",
    className: "bg-critical/10 text-critical border-critical/30",
  },
  "2": {
    label: "Sideways",
    className: "bg-bg text-text-secondary border-border",
  },
};

function normalize(value: string | null | undefined): RegimeKey | null {
  if (value == null) return null;
  const v = String(value).trim().toLowerCase();
  if (v === "0" || v.includes("bull") || v.includes("low")) return "0";
  if (v === "1" || v.includes("bear") || v.includes("high")) return "1";
  if (v === "2" || v.includes("side") || v.includes("range")) return "2";
  return null;
}

export function RegimePill() {
  const { data } = useQuery({
    queryKey: ["bot-status"],
    queryFn: getBotStatus,
    refetchInterval: 15_000,
  });

  const key = normalize(data?.current_regime);
  const meta = key ? REGIME[key] : { label: "Unknown", className: "bg-bg text-text-secondary border-border" };

  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${meta.className}`}
    >
      {meta.label}
    </span>
  );
}
