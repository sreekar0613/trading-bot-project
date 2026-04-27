import axios from "axios";
import type {
  AccountPayload,
  BotStatusPayload,
  MetricsPayload,
  PositionPayload,
  TradePayload,
  UniversePayload,
} from "@/types/api";

const baseURL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

let _getToken: (() => Promise<string>) | null = null;
export function registerTokenGetter(fn: () => Promise<string>) {
  _getToken = fn;
}

export const apiClient = axios.create({
  baseURL,
  timeout: 10_000,
  headers: { "Content-Type": "application/json" },
});

apiClient.interceptors.request.use(async (config) => {
  if (_getToken) {
    try {
      const token = await _getToken();
      config.headers.Authorization = `Bearer ${token}`;
    } catch {
      // token fetch failed; request proceeds without auth header
    }
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 || error.response?.status === 403) {
      window.location.href = "/";
    }
    return Promise.reject(error);
  }
);

export async function getAccount(): Promise<AccountPayload> {
  const { data } = await apiClient.get<AccountPayload>("/api/account");
  return data;
}

export async function getPositions(): Promise<PositionPayload[]> {
  const { data } = await apiClient.get<PositionPayload[]>("/api/positions");
  return data;
}

export async function getTrades(): Promise<TradePayload[]> {
  const { data } = await apiClient.get<TradePayload[]>("/api/trades");
  return data;
}

export async function getMetrics(): Promise<MetricsPayload> {
  const { data } = await apiClient.get<MetricsPayload>("/api/metrics");
  return data;
}

export async function getUniverse(): Promise<UniversePayload[]> {
  const { data } = await apiClient.get<UniversePayload[]>("/api/universe");
  return data;
}

export async function getBotStatus(): Promise<BotStatusPayload> {
  const { data } = await apiClient.get<BotStatusPayload>("/api/bot/status");
  return data;
}

export interface KillBotResponse {
  ok: boolean;
  positions_closed?: number;
  orders_canceled?: number;
  message?: string;
}

export async function killBot(): Promise<KillBotResponse> {
  const { data } = await apiClient.post<KillBotResponse>("/api/bot/kill");
  return data;
}

export async function pauseBot(): Promise<BotStatusPayload> {
  const { data } = await apiClient.post<BotStatusPayload>("/api/bot/pause");
  return data;
}

export async function resumeBot(): Promise<BotStatusPayload> {
  const { data } = await apiClient.post<BotStatusPayload>("/api/bot/resume");
  return data;
}

export async function blacklistTicker(symbol: string): Promise<{ ok: boolean; symbol: string }> {
  const { data } = await apiClient.post<{ ok: boolean; symbol: string }>(
    `/api/universe/${encodeURIComponent(symbol)}/blacklist`,
  );
  return data;
}

export async function unblacklistTicker(symbol: string): Promise<{ ok: boolean; symbol: string }> {
  const { data } = await apiClient.delete<{ ok: boolean; symbol: string }>(
    `/api/universe/${encodeURIComponent(symbol)}/blacklist`,
  );
  return data;
}

export interface HistoryBar {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export async function getSymbolHistory(
  symbol: string,
  timeframe: string,
): Promise<{ bars: HistoryBar[] }> {
  try {
    const { data } = await apiClient.get<{ bars: HistoryBar[] }>(
      `/api/history/${encodeURIComponent(symbol)}`,
      { params: { timeframe } },
    );
    return data;
  } catch {
    return { bars: [] };
  }
}

export async function exitPosition(symbol: string): Promise<{ ok: boolean; symbol: string }> {
  const { data } = await apiClient.post<{ ok: boolean; symbol: string }>(
    `/api/positions/${encodeURIComponent(symbol)}/exit`,
  );
  return data;
}
