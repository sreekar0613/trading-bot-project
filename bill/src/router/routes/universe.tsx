import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/router/AppShell";
import { AuthGuard } from "@/router/AuthGuard";

export const Route = createFileRoute("/universe")({
  component: () => (
    <AuthGuard>
      <AppShell>
        <h2 className="font-display text-2xl">Universe</h2>
        <p className="mt-2 text-text-secondary">Page content TBD.</p>
      </AppShell>
    </AuthGuard>
  ),
});
