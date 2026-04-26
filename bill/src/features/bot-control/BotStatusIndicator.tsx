import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { getBotStatus } from "@/services/api";

type StatusKind = "active" | "paused" | "halted";

const COLOR: Record<StatusKind, string> = {
  active: "var(--accent-bull)",
  paused: "#f59e0b",
  halted: "var(--critical-action)",
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
      <span className="relative flex h-2.5 w-2.5">
        <motion.span
          className="absolute inline-flex h-full w-full rounded-full"
          style={{ background: color }}
          animate={{ opacity: [0.6, 0.15, 0.6], scale: [1, 1.6, 1] }}
          transition={{ duration: 1.8, repeat: Infinity, ease: "easeInOut" }}
        />
        <span className="relative inline-flex h-2.5 w-2.5 rounded-full" style={{ background: color }} />
      </span>
      <span>{LABEL[kind]}</span>
    </div>
  );
}
