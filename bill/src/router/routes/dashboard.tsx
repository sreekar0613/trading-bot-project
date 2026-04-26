import { createFileRoute } from "@tanstack/react-router";
import { motion } from "framer-motion";
import { AppShell } from "@/router/AppShell";
import { AuthGuard } from "@/router/AuthGuard";
import { EquityCurveChart } from "@/features/dashboard/EquityCurveChart";
import { MetricsCards } from "@/features/dashboard/MetricsCards";
import { TopPositionsWidget } from "@/features/dashboard/TopPositionsWidget";
import { BotStatusWidget } from "@/features/dashboard/BotStatusWidget";

export const Route = createFileRoute("/dashboard")({
  component: () => (
    <AuthGuard>
      <AppShell>
        <DashboardPage />
      </AppShell>
    </AuthGuard>
  ),
});

const fadeUp = {
  hidden: { opacity: 0, y: 16 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.2, duration: 0.35, ease: "easeOut" },
  }),
};

function DashboardPage() {
  return (
    <div className="mx-auto w-full max-w-[1400px]">
      <h1 className="mb-6 font-display text-3xl italic">Dashboard</h1>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <motion.div
          custom={0}
          initial="hidden"
          animate="visible"
          variants={fadeUp}
          className="flex flex-col gap-6 lg:col-span-2"
        >
          <EquityCurveChart />
          <MetricsCards />
        </motion.div>

        <motion.div
          custom={1}
          initial="hidden"
          animate="visible"
          variants={fadeUp}
          className="flex flex-col gap-6 lg:col-span-1"
        >
          <TopPositionsWidget />
          <BotStatusWidget />
        </motion.div>
      </div>
    </div>
  );
}
