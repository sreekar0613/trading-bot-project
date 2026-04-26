import type { HTMLAttributes } from "react";

type Tone = "neutral" | "bull" | "bear" | "warn" | "critical";

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: Tone;
}

const TONE_CLASSES: Record<Tone, string> = {
  neutral: "bg-bg text-text-secondary border-border",
  bull: "bg-bull/10 text-bull border-bull/30",
  bear: "bg-bear/10 text-bear border-bear/30",
  warn: "bg-amber-500/10 text-amber-600 border-amber-500/30",
  critical: "bg-critical/10 text-critical border-critical/30",
};

export function Badge({ tone = "neutral", className = "", ...rest }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${TONE_CLASSES[tone]} ${className}`}
      {...rest}
    />
  );
}
