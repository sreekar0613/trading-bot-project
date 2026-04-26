import { useQuery } from "@tanstack/react-query";
import { Badge } from "@/components/Badge";
import { getBotStatus } from "@/services/api";

export function RegimePill() {
  const { data } = useQuery({
    queryKey: ["bot-status"],
    queryFn: getBotStatus,
    refetchInterval: 15_000,
  });

  const regime = data?.current_regime ?? "unknown";
  return <Badge tone="neutral">Regime: {regime}</Badge>;
}
