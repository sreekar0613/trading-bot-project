import { useEffect, useState } from "react";
import * as RDialog from "@radix-ui/react-dialog";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, OctagonAlert, X } from "lucide-react";
import { Button } from "@/components/Button";
import { getAccount, getPositions, killBot } from "@/services/api";

const CONFIRM_PHRASE = "LIQUIDATE";

type Step = "preview" | "confirm";

export function KillSwitchButton() {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState<Step>("preview");
  const [typed, setTyped] = useState("");
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!open) {
      const t = setTimeout(() => {
        setStep("preview");
        setTyped("");
      }, 150);
      return () => clearTimeout(t);
    }
  }, [open]);

  const { data: positions } = useQuery({
    queryKey: ["positions"],
    queryFn: getPositions,
    enabled: open,
  });
  const { data: account } = useQuery({
    queryKey: ["account"],
    queryFn: getAccount,
    enabled: open,
  });

  const mutation = useMutation({
    mutationFn: killBot,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["bot-status"] });
      queryClient.invalidateQueries({ queryKey: ["positions"] });
      queryClient.invalidateQueries({ queryKey: ["account"] });
      setOpen(false);
    },
  });

  const positionCount = positions?.length ?? 0;
  const liquidationValue =
    positions?.reduce((sum, p) => sum + (p.market_value ?? 0), 0) ?? account?.portfolio_value ?? 0;

  const formatted = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(liquidationValue);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex items-center justify-center gap-2 rounded-md bg-critical px-4 text-sm font-semibold text-white transition-opacity hover:opacity-90"
        style={{ minHeight: 44 }}
      >
        <OctagonAlert size={16} />
        Kill Switch
      </button>

      <RDialog.Root open={open} onOpenChange={setOpen}>
        <RDialog.Portal>
          <RDialog.Overlay className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm data-[state=open]:animate-in data-[state=open]:fade-in-0" />
          <RDialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-card border border-border bg-surface p-6 shadow-xl focus:outline-none">
            <div className="flex items-start justify-between gap-4">
              <RDialog.Title className="font-display text-2xl italic">
                Emergency Shutdown
              </RDialog.Title>
              <RDialog.Close
                className="rounded-input p-1 text-text-secondary hover:bg-bg"
                aria-label="Close"
                disabled={mutation.isPending}
              >
                <X size={16} />
              </RDialog.Close>
            </div>

            {step === "preview" ? (
              <div className="mt-5">
                <RDialog.Description className="sr-only">
                  Review the impact before halting the bot.
                </RDialog.Description>

                <dl className="divide-y divide-border rounded-card border border-border">
                  <PreviewRow
                    label="Open Positions"
                    value={String(positionCount)}
                  />
                  <PreviewRow
                    label="Estimated Liquidation Value"
                    value={formatted}
                  />
                </dl>

                <p className="mt-4 rounded-input border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-700">
                  Market orders will be used. Expect 0.1–0.5% slippage per position.
                </p>

                <div className="mt-6 flex justify-end gap-2">
                  <Button variant="secondary" onClick={() => setOpen(false)}>
                    Cancel
                  </Button>
                  <Button variant="critical" onClick={() => setStep("confirm")}>
                    Continue →
                  </Button>
                </div>
              </div>
            ) : (
              <div className="mt-5">
                <RDialog.Description className="text-sm text-text-secondary">
                  Type{" "}
                  <span className="font-mono font-semibold text-text-primary">{CONFIRM_PHRASE}</span>{" "}
                  to confirm. This will cancel all orders, close all positions, and halt the bot until tomorrow's open.
                </RDialog.Description>

                <input
                  type="text"
                  value={typed}
                  onChange={(e) => setTyped(e.target.value)}
                  autoFocus
                  spellCheck={false}
                  autoComplete="off"
                  placeholder={CONFIRM_PHRASE}
                  className="mt-4 w-full rounded-input border border-border bg-bg px-3 py-2 font-mono text-sm tracking-wider text-text-primary outline-none focus:border-text-primary"
                  disabled={mutation.isPending}
                />

                {mutation.isError && (
                  <p className="mt-2 text-xs text-critical">
                    Failed to halt bot. Try again or contact operator.
                  </p>
                )}

                <div className="mt-6 flex justify-between gap-2">
                  <Button
                    variant="ghost"
                    onClick={() => setStep("preview")}
                    disabled={mutation.isPending}
                  >
                    ← Back
                  </Button>
                  <div className="flex gap-2">
                    <Button
                      variant="secondary"
                      onClick={() => setOpen(false)}
                      disabled={mutation.isPending}
                    >
                      Cancel
                    </Button>
                    <Button
                      variant="critical"
                      onClick={() => mutation.mutate()}
                      disabled={typed !== CONFIRM_PHRASE || mutation.isPending}
                    >
                      {mutation.isPending ? (
                        <>
                          <Loader2 size={14} className="animate-spin" />
                          Halting...
                        </>
                      ) : (
                        "Confirm Shutdown"
                      )}
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </RDialog.Content>
        </RDialog.Portal>
      </RDialog.Root>
    </>
  );
}

function PreviewRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between px-4 py-3">
      <dt className="text-sm text-text-secondary">{label}</dt>
      <dd className="text-sm font-semibold text-text-primary tabular-nums">{value}</dd>
    </div>
  );
}
