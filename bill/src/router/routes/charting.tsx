import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/router/AppShell";
import { AuthGuard } from "@/router/AuthGuard";
import { ChartingPage } from "@/features/charting/ChartingPage";

interface ChartingSearch {
  symbol: string;
  timeframe: string;
}

export const Route = createFileRoute("/charting")({
  validateSearch: (search: Record<string, unknown>): ChartingSearch => ({
    symbol:
      typeof search.symbol === "string" && search.symbol.length > 0
        ? search.symbol
        : "AAPL",
    timeframe:
      typeof search.timeframe === "string" && search.timeframe.length > 0
        ? search.timeframe
        : "1D",
  }),
  component: () => (
    <AuthGuard>
      <AppShell>
        <ChartingPage />
      </AppShell>
    </AuthGuard>
  ),
});
