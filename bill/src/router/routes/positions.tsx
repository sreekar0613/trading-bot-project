import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/router/AppShell";
import { AuthGuard } from "@/router/AuthGuard";
import { PositionsTable } from "@/features/positions/PositionsTable";
import { PauseToggle } from "@/features/bot-control/PauseToggle";

export const Route = createFileRoute("/positions")({
  component: () => (
    <AuthGuard>
      <AppShell>
        <PositionsPage />
      </AppShell>
    </AuthGuard>
  ),
});

function PositionsPage() {
  return (
    <div className="mx-auto w-full max-w-[1400px]">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="font-display text-3xl italic">Positions</h1>
        <PauseToggle />
      </div>
      <PositionsTable />
    </div>
  );
}
