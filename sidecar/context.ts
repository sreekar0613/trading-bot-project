const FASTAPI_URL = process.env.FASTAPI_URL?.trim() || "http://localhost:8000";

export async function fetchBotContext(): Promise<unknown> {
  const url = `${FASTAPI_URL}/api/sidecar/context`;
  try {
    const res = await fetch(url);
    if (!res.ok) {
      console.error(`fetchBotContext: HTTP ${res.status} from ${url}`);
      return { error: "context unavailable" };
    }
    return await res.json();
  } catch (err) {
    console.error(`fetchBotContext: failed to reach ${url}:`, err);
    return { error: "context unavailable" };
  }
}
