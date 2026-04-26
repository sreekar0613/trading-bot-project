import NumberFlow from "@number-flow/react";
import { useQuery } from "@tanstack/react-query";
import { getAccount } from "@/services/api";

export function AccountEquity() {
  const { data } = useQuery({
    queryKey: ["account"],
    queryFn: getAccount,
    refetchInterval: 10_000,
  });

  const equity = data?.equity ?? 0;

  return (
    <div className="flex flex-col text-right" data-numeric>
      <span className="text-[10px] uppercase tracking-wide text-text-secondary">Equity</span>
      <span className="font-semibold">
        <NumberFlow value={equity} format={{ style: "currency", currency: "USD" }} />
      </span>
    </div>
  );
}
