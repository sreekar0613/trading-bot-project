import { createFileRoute } from "@tanstack/react-router";
import { motion } from "framer-motion";
import { AppShell } from "@/router/AppShell";
import { AuthGuard } from "@/router/AuthGuard";
import { MetricsHero } from "@/features/metrics/MetricsHero";
import { MonthlyReturnsChart } from "@/features/metrics/MonthlyReturnsChart";
import { WinLossChart } from "@/features/metrics/WinLossChart";
import { TradeCountProgress } from "@/features/metrics/TradeCountProgress";
import { PnLBreakdownTable } from "@/features/metrics/PnLBreakdownTable";

export const Route = createFileRoute("/metrics")({
  component: () => (
    <AuthGuard>
      <AppShell>
        <MetricsPage />
      </AppShell>
    </AuthGuard>
  ),
});

const fadeUp = {
  hidden: { opacity: 0, y: 16 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.12, duration: 0.35, ease: "easeOut" },
  }),
};

function MetricsPage() {
  return (
    <div className="mx-auto w-full max-w-[1400px]">
      <header className="mb-6">
        <h1 className="font-display text-3xl italic">Metrics</h1>
        <p className="mt-1 text-sm text-text-secondary">
          backtest 2020–2024 · RSI&lt;40 variant
        </p>
      </header>

      <div className="flex flex-col gap-6">
        <motion.div custom={0} initial="hidden" animate="visible" variants={fadeUp}>
          <MetricsHero />
        </motion.div>

        <motion.div custom={1} initial="hidden" animate="visible" variants={fadeUp}>
          <TradeCountProgress />
        </motion.div>

        <motion.div
          custom={2}
          initial="hidden"
          animate="visible"
          variants={fadeUp}
          className="grid grid-cols-1 gap-6 lg:grid-cols-3"
        >
          <div className="lg:col-span-2">
            <MonthlyReturnsChart />
          </div>
          <div className="lg:col-span-1">
            <WinLossChart />
          </div>
        </motion.div>

        <motion.div custom={3} initial="hidden" animate="visible" variants={fadeUp}>
          <PnLBreakdownTable />
        </motion.div>
      </div>
    </div>
  );
}
