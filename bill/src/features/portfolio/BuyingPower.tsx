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
    <div className="flex flex-col text-right text-text-secondary" data-numeric>
      <span className="text-[10px] uppercase tracking-wide">Buying power</span>
      <span className="text-sm">
        <NumberFlow value={bp} format={{ style: "currency", currency: "USD" }} />
      </span>
    </div>
  );
}
