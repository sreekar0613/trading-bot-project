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

export const apiClient = axios.create({
  baseURL,
  timeout: 10_000,
  headers: { "Content-Type": "application/json" },
});

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
