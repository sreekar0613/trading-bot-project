import { createFileRoute } from "@tanstack/react-router";
import { motion } from "framer-motion";
import { AppShell } from "@/router/AppShell";
import { AuthGuard } from "@/router/AuthGuard";
import { TradesTable } from "@/features/trades/TradesTable";
import { CSVExport } from "@/features/trades/CSVExport";

export const Route = createFileRoute("/trades")({
  component: () => (
    <AuthGuard>
      <AppShell>
        <TradesPage />
      </AppShell>
    </AuthGuard>
  ),
});

function TradesPage() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      className="mx-auto w-full max-w-[1400px]"
    >
      <header className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-3xl italic">Trades</h1>
          <p className="mt-1 text-sm text-text-secondary">execution ledger</p>
        </div>
        <CSVExport />
      </header>
      <TradesTable />
    </motion.div>
  );
}
