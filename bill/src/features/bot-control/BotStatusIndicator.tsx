import { useQuery } from "@tanstack/react-query";
import { getBotStatus } from "@/services/api";

type StatusKind = "active" | "paused" | "halted";

const COLOR: Record<StatusKind, string> = {
  active: "#00C805",
  paused: "#F59E0B",
  halted: "#D93025",
};

const LABEL: Record<StatusKind, string> = {
  active: "Active",
  paused: "Paused",
  halted: "Halted",
};

function deriveStatus(data: Awaited<ReturnType<typeof getBotStatus>> | undefined): StatusKind {
  if (!data) return "paused";
  if (data.halted) return "halted";
  if (data.paused) return "paused";
  return "active";
}

export function BotStatusIndicator() {
  const { data } = useQuery({
    queryKey: ["bot-status"],
    queryFn: getBotStatus,
    refetchInterval: 5_000,
  });

  const kind = deriveStatus(data);
  const color = COLOR[kind];

  return (
    <div className="flex items-center gap-2 text-sm text-text-secondary">
      <span className="relative inline-flex h-2.5 w-2.5">
        <span
          className="bill-pulse-ring absolute inset-0 rounded-full"
          style={{ background: color }}
          aria-hidden
        />
        <span
          className="relative inline-flex h-2.5 w-2.5 rounded-full"
          style={{ background: color }}
        />
      </span>
      <span className="text-text-primary">{LABEL[kind]}</span>
    </div>
  );
}
