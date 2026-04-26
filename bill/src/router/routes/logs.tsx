import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/router/AppShell";
import { AuthGuard } from "@/router/AuthGuard";
import { LogsTerminal } from "@/features/logs/LogsTerminal";

export const Route = createFileRoute("/logs")({
  component: () => (
    <AuthGuard>
      <AppShell>
        <LogsPage />
      </AppShell>
    </AuthGuard>
  ),
});

function LogsPage() {
  return (
    <div className="mx-auto flex w-full max-w-[1400px] flex-col">
      <header className="mb-4">
        <h1 className="font-display text-3xl italic">Logs</h1>
        <p className="mt-1 text-sm text-text-secondary">
          paper_trading.log · live stream
        </p>
      </header>
      <LogsTerminal />
    </div>
  );
}
