import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { getTrades } from "@/services/api";
import { useAuth0 } from "@auth0/auth0-react";
import { useNavigate } from "@tanstack/react-router";

export const Route = createFileRoute("/")({
  component: PublicHomePage,
});

const sectionVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.15, duration: 0.4, ease: "easeOut" },
  }),
};

function Section({ index, children, className = "" }: { index: number; children: React.ReactNode; className?: string }) {
  return (
    <motion.section
      custom={index}
      initial="hidden"
      animate="visible"
      variants={sectionVariants}
      className={className}
    >
      {children}
    </motion.section>
  );
}

function PublicHomePage() {
  const { data: trades } = useQuery({
    queryKey: ["trades"],
    queryFn: getTrades,
    retry: false,
    staleTime: 60_000,
  });

  const tradesCount = trades?.length;
  const { isAuthenticated, loginWithRedirect } = useAuth0();
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-bg text-text-primary">
      <div className="mx-auto flex min-h-screen max-w-[680px] flex-col px-6 py-24">
        <Section index={0} className="mb-24">
          <h1 className="font-display text-[56px] italic leading-none tracking-tight">
            Bill
          </h1>
          <p className="mt-6 text-lg text-text-secondary">
            An autonomous multi-factor equity trading bot running live on paper capital.
          </p>
        </Section>

        <Section index={1} className="mb-24">
          <div className="grid grid-cols-3 gap-8 border-y border-border py-8">
            <Stat label="Target Return" value="8–15%" suffix="annually" />
            <Stat label="Starting Capital" value="$1,100" />
            <Stat
              label="Trades to Date"
              value={tradesCount !== undefined ? String(tradesCount) : "—"}
            />
          </div>
        </Section>

        <Section index={2} className="mb-24 space-y-5 text-[15px] leading-relaxed text-text-primary">
          <h2 className="mb-6 font-display text-2xl italic">How it works</h2>
          <p>
            Bill enters positions only when four signals agree. RSI must read below 40, MACD must cross above its signal line, price must touch the lower Bollinger band, and the stock must trade above its 200-day exponential moving average. Confluence over conviction — no single indicator can pull the trigger alone.
          </p>
          <p>
            Position sizing is volatility-adjusted using the Average True Range. Each trade risks a fixed fraction of equity, with the share count derived from a 2.5× ATR stop distance. Volatile names get smaller allocations; stable names get larger ones. The math, not the mood, decides size.
          </p>
          <p>
            A three-state Hidden Markov Model continuously classifies the broader market into trending, ranging, or risk-off regimes. Bill adjusts its appetite accordingly — leaning into entries when the regime is constructive, throttling back when conditions deteriorate. The model retrains weekly on rolling returns and volatility features.
          </p>
          <p>
            A layered kill switch guards the account at every level. Per-trade ATR trailing stops protect individual positions, a 5% session loss halts the bot for the day, and a 15% drawdown from peak pauses new entries entirely. Safety is not optional and not negotiable.
          </p>
        </Section>

        <Section index={3} className="mb-24">
          <div className="text-sm text-text-secondary">
            <span className="mr-2 font-medium text-text-primary">Stack</span>
            Python 3.13 · Alpaca · SQLite · FastAPI · React · Vite
          </div>
        </Section>

        <Section index={4} className="mb-24">
          <div className="flex flex-wrap gap-3">
            <a
              href="https://github.com/sreekar0613/trading-bot-project"
              target="_blank"
              rel="noreferrer"
              className="rounded-input border border-border bg-transparent px-5 py-2.5 text-sm font-medium text-text-primary transition-colors hover:bg-surface"
            >
              View GitHub
            </a>
            <button
              onClick={() =>
                isAuthenticated
                  ? navigate({ to: "/dashboard" })
                  : loginWithRedirect({ 
                      appState: { returnTo: "/dashboard" },
                      authorizationParams: { prompt: "login" }
                    })
              }
              className="rounded-input bg-text-primary px-5 py-2.5 text-sm font-medium text-white transition-opacity hover:opacity-90"
            >
              Open Dashboard →
            </button>
          </div>
        </Section>

        <Section index={5} className="mt-auto">
          <p className="border-t border-border pt-6 text-xs text-text-secondary">
            Built by Sreekar Kakumani · Paper trading only · Not financial advice
          </p>
        </Section>
      </div>
    </div>
  );
}

function Stat({ label, value, suffix }: { label: string; value: string; suffix?: string }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-text-secondary">{label}</div>
      <div className="mt-2 font-display text-2xl tabular-nums">{value}</div>
      {suffix && <div className="mt-1 text-xs text-text-secondary">{suffix}</div>}
    </div>
  );
}
