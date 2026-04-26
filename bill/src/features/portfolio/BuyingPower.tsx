import NumberFlow from "@number-flow/react";
import { useQuery } from "@tanstack/react-query";
import { getAccount } from "@/services/api";

export function BuyingPower() {
  const { data } = useQuery({
    queryKey: ["account"],
    queryFn: getAccount,
    refetchInterval: 10_000,
  });

  const bp = data?.buying_power ?? 0;

  return (
    <div className="flex flex-col text-right" data-numeric>
      <span className="text-[10px] uppercase tracking-wide text-text-secondary">Buying Power</span>
      <span className="text-sm text-text-primary">
        <NumberFlow value={bp} format={{ style: "currency", currency: "USD" }} />
      </span>
    </div>
  );
}
