import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/router/AppShell";
import { AuthGuard } from "@/router/AuthGuard";

export const Route = createFileRoute("/charting")({
  component: () => (
    <AuthGuard>
      <AppShell>
        <h2 className="font-display text-2xl">Charting</h2>
        <p className="mt-2 text-text-secondary">Page content TBD.</p>
      </AppShell>
    </AuthGuard>
  ),
});
