import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { getTrades } from "@/services/api";

const TARGET = 200;

export function TradeCountProgress() {
  const { data: trades } = useQuery({
    queryKey: ["trades"],
    queryFn: getTrades,
    refetchInterval: 60_000,
  });

  const count = trades?.length ?? 0;
  const pct = Math.min(100, (count / TARGET) * 100);

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="mb-2 flex items-baseline justify-between text-xs">
        <span className="font-medium text-text-primary">Trade Count</span>
        <span className="tabular-nums text-text-secondary">
          {count} / {TARGET}
        </span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-border">
        <motion.div
          className="h-full rounded-full bg-bull"
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.6, ease: "easeOut" }}
        />
      </div>
      <div className="mt-2 text-xs text-text-secondary">
        Institutional threshold: 200 trades
      </div>
    </div>
  );
}
