import { useEffect, useMemo, useRef, useState } from "react";
import {
  createChart,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";
import { useQuery } from "@tanstack/react-query";
import { getAccount } from "@/services/api";

type Timeframe = "1W" | "1M" | "3M" | "6M" | "1Y" | "All";

const TIMEFRAMES: Timeframe[] = ["1W", "1M", "3M", "6M", "1Y", "All"];

const TIMEFRAME_DAYS: Record<Timeframe, number | null> = {
  "1W": 7,
  "1M": 30,
  "3M": 90,
  "6M": 180,
  "1Y": 365,
  All: null,
};

const FULL_DAYS = 730;

// MOCK series — replace with /api/history/portfolio once that endpoint ships.
function buildMockCurve(currentEquity: number) {
  const now = Math.floor(Date.now() / 1000);
  const points: { time: UTCTimestamp; value: number }[] = [];
  let v = currentEquity * 0.6;
  for (let i = FULL_DAYS; i >= 0; i--) {
    const drift = 0.0015;
    const shock = (Math.sin(i * 0.7) + Math.cos(i * 0.31)) * 0.004;
    v = v * (1 + drift + shock);
    points.push({
      time: (now - i * 86_400) as UTCTimestamp,
      value: +v.toFixed(2),
    });
  }
  const last = points[points.length - 1];
  if (last) last.value = currentEquity;
  return points;
}

export function EquityCurveChart() {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Area"> | null>(null);

  const [timeframe, setTimeframe] = useState<Timeframe>("3M");

  const { data: account } = useQuery({
    queryKey: ["account"],
    queryFn: getAccount,
    refetchInterval: 10_000,
  });

  const equity = account?.equity ?? 1100;
  const fullSeries = useMemo(() => buildMockCurve(equity), [equity]);

  const series = useMemo(() => {
    const days = TIMEFRAME_DAYS[timeframe];
    if (days == null) return fullSeries;
    return fullSeries.slice(-Math.min(days + 1, fullSeries.length));
  }, [fullSeries, timeframe]);

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: 280,
      layout: {
        background: { color: "transparent" },
        textColor: "#737373",
        fontFamily: "Geist, system-ui, sans-serif",
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { visible: false },
      },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false, fixLeftEdge: true, fixRightEdge: true },
      handleScroll: false,
      handleScale: false,
      crosshair: { vertLine: { visible: false }, horzLine: { visible: false } },
    });
    const area = chart.addAreaSeries({
      lineColor: "#00C805",
      topColor: "rgba(0, 200, 5, 0.20)",
      bottomColor: "rgba(0, 200, 5, 0.00)",
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    });

    chartRef.current = chart;
    seriesRef.current = area;

    const ro = new ResizeObserver(() => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ width: containerRef.current.clientWidth });
      }
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!seriesRef.current) return;
    seriesRef.current.setData(series);
    chartRef.current?.timeScale().fitContent();
  }, [series]);

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="mb-3 flex items-baseline justify-between">
        <h3 className="text-sm font-medium text-text-primary">Equity Curve</h3>
        <span className="text-xs text-text-secondary">{timeframe} · mock data</span>
      </div>
      <div className="mb-3 flex flex-wrap gap-1.5">
        {TIMEFRAMES.map((tf) => {
          const active = tf === timeframe;
          return (
            <button
              key={tf}
              type="button"
              onClick={() => setTimeframe(tf)}
              className={`h-7 rounded-full px-3 text-xs transition-colors ${
                active
                  ? "bg-text-primary text-white"
                  : "border border-border bg-transparent text-text-secondary hover:text-text-primary"
              }`}
            >
              {tf}
            </button>
          );
        })}
      </div>
      <div ref={containerRef} style={{ height: 280 }} />
    </div>
  );
}
