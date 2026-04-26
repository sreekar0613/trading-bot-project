export interface AccountPayload {
  equity: number;
  cash: number;
  buying_power: number;
  portfolio_value: number;
  last_equity?: number;
  status?: string;
}

export interface PositionPayload {
  symbol: string;
  qty: number;
  avg_entry_price: number;
  current_price: number;
  market_value: number;
  unrealized_pl: number;
  unrealized_plpc: number;
  side: "long" | "short";
}

export interface TradePayload {
  id: string | number;
  symbol: string;
  side: "buy" | "sell";
  qty: number;
  price: number;
  timestamp: string;
  reason?: string;
  realized_pnl?: number | null;
}

export interface MetricsPayload {
  sharpe_ratio: number | null;
  max_drawdown: number | null;
  win_rate: number | null;
  profit_factor: number | null;
  total_return: number | null;
  recovery_factor: number | null;
  equity_curve?: { date: string; equity: number }[];
}

export interface UniversePayload {
  symbol: string;
  market_cap: number | null;
  roe: number | null;
  pb_ratio: number | null;
  avg_volume: number | null;
  earnings_growth: number | null;
  blacklisted?: boolean;
}

export interface BotStatusPayload {
  paused: boolean;
  halted: boolean;
  last_heartbeat: string | null;
  open_position_count: number;
  current_regime: string | null;
  last_updated?: string | null;
}

export interface LogLine {
  type: "log" | "error";
  timestamp: string;
  level: "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL";
  message: string;
}
