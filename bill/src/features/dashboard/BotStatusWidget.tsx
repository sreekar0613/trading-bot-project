import { useQuery } from "@tanstack/react-query";
import { getBotStatus } from "@/services/api";
import type { BotStatusPayload } from "@/types/api";

type StatusKind = "active" | "paused" | "halted";

const STATUS_META: Record<StatusKind, { label: string; dot: string; text: string }> = {
  active: { label: "Active", dot: "#00C805", text: "text-bull" },
  paused: { label: "Paused", dot: "#F59E0B", text: "text-amber-600" },
  halted: { label: "Halted", dot: "#D93025", text: "text-critical" },
};

function deriveKind(d: BotStatusPayload | undefined): StatusKind {
  if (!d) return "paused";
  if (d.halted) return "halted";
  if (d.paused) return "paused";
  return "active";
}

function formatHeartbeat(iso: string | null | undefined) {
  if (!iso) return "—";
  const ts = new Date(iso).getTime();
  if (Number.isNaN(ts)) return iso;
  const diffSec = Math.round((Date.now() - ts) / 1000);
  if (diffSec < 60) return `${diffSec}s ago`;
  if (diffSec < 3600) return `${Math.round(diffSec / 60)}m ago`;
  return new Date(ts).toLocaleString();
}

function formatHaltedUntil(iso: string | null | undefined) {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}

export function BotStatusWidget() {
  const { data } = useQuery({
    queryKey: ["bot-status"],
    queryFn: getBotStatus,
    refetchInterval: 30_000,
  });

  const kind = deriveKind(data);
  const meta = STATUS_META[kind];
  const haltedUntil = formatHaltedUntil(
    (data as (BotStatusPayload & { halted_until?: string | null }) | undefined)?.halted_until,
  );

  return (
    <div className="rounded-lg border border-border bg-surface">
      <div className="border-b border-border px-4 py-3">
        <h3 className="text-sm font-medium text-text-primary">Bot Status</h3>
      </div>
      <dl className="divide-y divide-border text-sm">
        <Row label="Status">
          <span className="inline-flex items-center gap-2">
            <span
              className="inline-block h-2 w-2 rounded-full"
              style={{ background: meta.dot }}
              aria-hidden
            />
            <span className={`font-medium ${meta.text}`}>{meta.label}</span>
          </span>
        </Row>
        <Row label="Current Regime">
          <span className="text-text-primary">{data?.current_regime ?? "—"}</span>
        </Row>
        <Row label="Last Heartbeat">
          <span className="text-text-primary tabular-nums">
            {formatHeartbeat(data?.last_heartbeat)}
          </span>
        </Row>
        {haltedUntil && (
          <Row label="Halted Until">
            <span className="text-critical tabular-nums">{haltedUntil}</span>
          </Row>
        )}
      </dl>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between px-4 py-3">
      <dt className="text-text-secondary">{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}
