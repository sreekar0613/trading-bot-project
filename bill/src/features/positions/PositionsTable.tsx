import { useState } from "react";
import * as RDialog from "@radix-ui/react-dialog";
import NumberFlow from "@number-flow/react";
import { AnimatePresence, motion } from "framer-motion";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { X } from "lucide-react";
import { exitPosition, getPositions } from "@/services/api";
import { usePositionStore } from "@/store/positionStore";
import { SlideToConfirm } from "@/components/SlideToConfirm";
import type { PositionPayload } from "@/types/api";

const usd = { style: "currency", currency: "USD" } as const;
const pct = { style: "percent", maximumFractionDigits: 2, signDisplay: "always" } as const;
const usdSigned = { ...usd, signDisplay: "always" } as const;

export function PositionsTable() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["positions"],
    queryFn: getPositions,
    refetchInterval: 30_000,
  });

  const wsBySymbol = usePositionStore((s) => s.bySymbol);
  const merged: PositionPayload[] = (data ?? []).map((p) => wsBySymbol[p.symbol] ?? p);

  const [pendingExit, setPendingExit] = useState<PositionPayload | null>(null);
  const [exitingSymbols, setExitingSymbols] = useState<Set<string>>(new Set());

  const exitMutation = useMutation({
    mutationFn: (symbol: string) => exitPosition(symbol),
    onSuccess: (_res, symbol) => {
      setExitingSymbols((s) => new Set(s).add(symbol));
      setPendingExit(null);
      // Allow exit animation to play before refetching.
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ["positions"] });
      }, 350);
    },
  });

  if (!isLoading && merged.length === 0) {
    return (
      <div className="flex min-h-[280px] items-center justify-center">
        <p className="font-display text-xl italic text-text-secondary">No open positions</p>
      </div>
    );
  }

  return (
    <>
      <div className="w-full overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr className="border-b border-border">
              <Th className="text-left">Ticker</Th>
              <Th className="text-right">Entry</Th>
              <Th className="text-right">Current</Th>
              <Th className="text-right">Size</Th>
              <Th className="text-right">Market Value</Th>
              <Th className="text-right">PnL ($)</Th>
              <Th className="text-right">PnL (%)</Th>
              <Th className="text-right">Action</Th>
            </tr>
          </thead>
          <tbody>
            <AnimatePresence initial={false}>
              {merged.map((p, i) => {
                if (exitingSymbols.has(p.symbol)) return null;
                const positive = p.unrealized_pl >= 0;
                const tone = positive ? "text-bull" : "text-critical";
                return (
                  <motion.tr
                    key={p.symbol}
                    layout
                    initial={{ opacity: 1 }}
                    exit={{ opacity: 0, x: 24, transition: { duration: 0.25, ease: "easeOut" } }}
                    className={`h-12 border-b border-border ${
                      i % 2 === 0 ? "bg-bg" : "bg-surface"
                    }`}
                  >
                    <Td className="text-left font-semibold text-text-primary">{p.symbol}</Td>
                    <NumTd>
                      <NumberFlow value={p.avg_entry_price} format={usd} />
                    </NumTd>
                    <NumTd>
                      <NumberFlow value={p.current_price} format={usd} />
                    </NumTd>
                    <NumTd>
                      <NumberFlow
                        value={p.qty}
                        format={{ maximumFractionDigits: 4 }}
                      />
                    </NumTd>
                    <NumTd>
                      <NumberFlow value={p.market_value} format={usd} />
                    </NumTd>
                    <NumTd className={tone + " font-medium"}>
                      <NumberFlow value={p.unrealized_pl} format={usdSigned} />
                    </NumTd>
                    <NumTd className={tone + " font-medium"}>
                      <NumberFlow value={p.unrealized_plpc} format={pct} />
                    </NumTd>
                    <Td className="text-right">
                      <button
                        type="button"
                        onClick={() => setPendingExit(p)}
                        className="inline-flex h-8 items-center rounded-input border border-border bg-transparent px-3 text-xs font-medium text-text-secondary transition-colors hover:border-critical hover:text-critical"
                      >
                        Exit
                      </button>
                    </Td>
                  </motion.tr>
                );
              })}
            </AnimatePresence>
          </tbody>
        </table>
      </div>

      <RDialog.Root
        open={!!pendingExit}
        onOpenChange={(open) => {
          if (!open && !exitMutation.isPending) setPendingExit(null);
        }}
      >
        <RDialog.Portal>
          <RDialog.Overlay className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm data-[state=open]:animate-in data-[state=open]:fade-in-0" />
          <RDialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-card border border-border bg-surface p-6 shadow-xl focus:outline-none">
            <div className="flex items-start justify-between gap-4">
              <RDialog.Title className="font-display text-2xl italic">
                Force Exit {pendingExit?.symbol}
              </RDialog.Title>
              <RDialog.Close
                className="rounded-input p-1 text-text-secondary hover:bg-bg disabled:opacity-50"
                aria-label="Close"
                disabled={exitMutation.isPending}
              >
                <X size={16} />
              </RDialog.Close>
            </div>
            <RDialog.Description className="mt-2 text-sm text-text-secondary">
              Submits a market order to close the entire position immediately. Slippage may apply.
            </RDialog.Description>

            {pendingExit && (
              <div className="mt-5">
                <SlideToConfirm
                  label={`Slide to exit ${pendingExit.symbol}`}
                  loading={exitMutation.isPending}
                  onConfirm={async () => {
                    await exitMutation.mutateAsync(pendingExit.symbol);
                  }}
                />
                {exitMutation.isError && (
                  <p className="mt-2 text-xs text-critical">
                    Exit failed. Verify with broker before retrying.
                  </p>
                )}
              </div>
            )}
          </RDialog.Content>
        </RDialog.Portal>
      </RDialog.Root>
    </>
  );
}

function Th({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <th
      className={`px-3 py-2 text-[11px] font-medium uppercase tracking-wide text-text-secondary ${className}`}
    >
      {children}
    </th>
  );
}

function Td({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <td className={`px-3 ${className}`}>{children}</td>;
}

function NumTd({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <td className={`px-3 text-right tabular-nums ${className}`} data-numeric>
      {children}
    </td>
  );
}
