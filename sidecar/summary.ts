import { askGemini } from "./llm.js";

const SUMMARY_PROMPT =
  "Generate a concise end-of-day summary of today's trading bot activity. " +
  "Include: portfolio value and daily PnL%, any positions opened or closed today, " +
  "any signals generated, any circuit breaker or earnings filter triggers, " +
  "and overall bot health. Keep it under 200 words.";

export async function buildDailySummary(context: unknown): Promise<string> {
  return askGemini(SUMMARY_PROMPT, context);
}
