import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/router/AppShell";
import { AuthGuard } from "@/router/AuthGuard";
import { UniverseTable } from "@/features/universe/UniverseTable";

export const Route = createFileRoute("/universe")({
  component: () => (
    <AuthGuard>
      <AppShell>
        <UniversePage />
      </AppShell>
    </AuthGuard>
  ),
});

function UniversePage() {
  return (
    <div className="mx-auto w-full max-w-[1400px]">
      <header className="mb-6">
        <h1 className="font-display text-3xl italic">Universe</h1>
        <p className="mt-1 text-sm text-text-secondary">
          fundamental screener · updated weekly
        </p>
      </header>
      <UniverseTable />
    </div>
  );
}
