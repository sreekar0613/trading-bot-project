import { createFileRoute, Link } from "@tanstack/react-router";

export const Route = createFileRoute("/")({
  component: PublicHomePage,
});

function PublicHomePage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 px-6 text-center">
      <h1 className="font-display text-5xl italic">Bill</h1>
      <p className="max-w-md text-text-secondary">
        An autonomous equity trading bot. Sign in to view the live dashboard.
      </p>
      <Link
        to="/dashboard"
        className="rounded-input bg-text-primary px-5 py-2.5 text-sm font-medium text-white"
      >
        Open dashboard
      </Link>
    </div>
  );
}
