import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearch } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import * as RToggle from "@radix-ui/react-toggle";
import {
  createChart,
  type IChartApi,
  type ISeriesApi,
  type SeriesMarker,
  type Time,
  type UTCTimestamp,
} from "lightweight-charts";
import { getSymbolHistory, getTrades, getUniverse } from "@/services/api";

const TIMEFRAMES = ["1D", "1W", "1M", "3M", "6M", "1Y"] as const;
type Timeframe = (typeof TIMEFRAMES)[number];

const FALLBACK_SYMBOLS = ["AAPL", "MSFT", "NVDA", "GOOGL", "META", "JPM", "V"];

function calcEMA(values: number[], period: number): (number | null)[] {
  const k = 2 / (period + 1);
  const out: (number | null)[] = [];
  let ema: number | null = null;
  let sum = 0;
  for (let i = 0; i < values.length; i++) {
    const v = values[i] as number;
    if (i < period) {
      sum += v;
      if (i === period - 1) {
        ema = sum / period;
        out.push(ema);
      } else {
        out.push(null);
      }
    } else {
      ema = v * k + (ema as number) * (1 - k);
      out.push(ema);
    }
  }
  return out;
}

function calcBB(values: number[], period = 20, mult = 2) {
  const upper: (number | null)[] = [];
  const mid: (number | null)[] = [];
  const lower: (number | null)[] = [];
  for (let i = 0; i < values.length; i++) {
    if (i < period - 1) {
      upper.push(null);
      mid.push(null);
      lower.push(null);
      continue;
    }
    let s = 0;
    for (let j = i - period + 1; j <= i; j++) s += values[j] as number;
    const m = s / period;
    let varSum = 0;
    for (let j = i - period + 1; j <= i; j++) {
      const d = (values[j] as number) - m;
      varSum += d * d;
    }
    const sd = Math.sqrt(varSum / period);
    mid.push(m);
    upper.push(m + mult * sd);
    lower.push(m - mult * sd);
  }
  return { upper, mid, lower };
}

export function ChartingPage() {
  const search = useSearch({ from: "/charting" });
  const navigate = useNavigate({ from: "/charting" });
  const symbol = search.symbol;
  const timeframe = search.timeframe as Timeframe;

  const [showEma, setShowEma] = useState(true);
  const [showBB, setShowBB] = useState(false);
  const [showVol, setShowVol] = useState(true);

  const setSymbol = (s: string) =>
    navigate({ search: (prev) => ({ ...prev, symbol: s }) });
  const setTimeframe = (tf: string) =>
    navigate({ search: (prev) => ({ ...prev, timeframe: tf }) });

  // Universe for symbol combobox
  const { data: universe } = useQuery({
    queryKey: ["universe"],
    queryFn: getUniverse,
  });
  const symbols = useMemo(() => {
    const list = (universe ?? []).map((u) => u.symbol).filter(Boolean);
    return list.length ? list : FALLBACK_SYMBOLS;
  }, [universe]);

  const [comboOpen, setComboOpen] = useState(false);
  const [query, setQuery] = useState("");
  const comboRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!comboOpen) return;
    const onDoc = (e: MouseEvent) => {
      if (comboRef.current && !comboRef.current.contains(e.target as Node)) {
        setComboOpen(false);
      }
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [comboOpen]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return symbols.slice(0, 200);
    return symbols.filter((s) => s.toLowerCase().includes(q)).slice(0, 200);
  }, [symbols, query]);

  // History data
  const { data: history, isLoading } = useQuery({
    queryKey: ["history", symbol, timeframe],
    queryFn: () => getSymbolHistory(symbol, timeframe),
  });
  const bars = history?.bars ?? [];

  const { data: trades } = useQuery({
    queryKey: ["trades"],
    queryFn: getTrades,
  });

  // Chart instance
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const emaRef = useRef<ISeriesApi<"Line"> | null>(null);
  const bbUpperRef = useRef<ISeriesApi<"Line"> | null>(null);
  const bbMidRef = useRef<ISeriesApi<"Line"> | null>(null);
  const bbLowerRef = useRef<ISeriesApi<"Line"> | null>(null);
  const volRef = useRef<ISeriesApi<"Histogram"> | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,
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
      timeScale: { borderVisible: false },
    });
    const candle = chart.addCandlestickSeries({
      upColor: "#00C805",
      downColor: "#FF5000",
      borderVisible: false,
      wickUpColor: "#00C805",
      wickDownColor: "#FF5000",
    });
    chartRef.current = chart;
    candleRef.current = candle;

    const ro = new ResizeObserver(() => {
      if (!containerRef.current || !chartRef.current) return;
      chartRef.current.applyOptions({
        width: containerRef.current.clientWidth,
        height: containerRef.current.clientHeight,
      });
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      candleRef.current = null;
      emaRef.current = null;
      bbUpperRef.current = null;
      bbMidRef.current = null;
      bbLowerRef.current = null;
      volRef.current = null;
    };
  }, []);

  // Candle data + markers
  useEffect(() => {
    if (!candleRef.current || !chartRef.current) return;
    const data = bars.map((b) => ({
      time: b.time as UTCTimestamp,
      open: b.open,
      high: b.high,
      low: b.low,
      close: b.close,
    }));
    candleRef.current.setData(data);

    const myTrades = (trades ?? []).filter((t) => t.symbol === symbol);
    const markers: SeriesMarker<Time>[] = myTrades
      .map((t) => {
        const epoch = Math.floor(new Date(t.timestamp).getTime() / 1000);
        return {
          time: epoch as UTCTimestamp,
          position: (t.side === "buy" ? "belowBar" : "aboveBar") as
            | "belowBar"
            | "aboveBar",
          color: t.side === "buy" ? "#00C805" : "#FF5000",
          shape: (t.side === "buy" ? "arrowUp" : "arrowDown") as
            | "arrowUp"
            | "arrowDown",
          size: 1,
        };
      })
      .sort((a, b) => (a.time as number) - (b.time as number));
    candleRef.current.setMarkers(markers);

    if (data.length) chartRef.current.timeScale().fitContent();
  }, [bars, trades, symbol]);

  // EMA 200 overlay
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    if (showEma && bars.length >= 200) {
      if (!emaRef.current) {
        emaRef.current = chart.addLineSeries({
          color: "#737373",
          lineWidth: 1,
          lineStyle: 1,
          priceLineVisible: false,
          lastValueVisible: false,
        });
      }
      const closes = bars.map((b) => b.close);
      const ema = calcEMA(closes, 200);
      const series: { time: UTCTimestamp; value: number }[] = [];
      for (let i = 0; i < bars.length; i++) {
        const v = ema[i];
        if (v != null)
          series.push({ time: bars[i]!.time as UTCTimestamp, value: v });
      }
      emaRef.current.setData(series);
    } else if (emaRef.current) {
      chart.removeSeries(emaRef.current);
      emaRef.current = null;
    }
  }, [showEma, bars]);

  // Bollinger Bands overlay
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    if (showBB && bars.length >= 20) {
      const bbColor = "rgba(115,115,115,0.5)";
      const opts = {
        color: bbColor,
        lineWidth: 1 as const,
        priceLineVisible: false,
        lastValueVisible: false,
      };
      if (!bbUpperRef.current) bbUpperRef.current = chart.addLineSeries(opts);
      if (!bbMidRef.current) bbMidRef.current = chart.addLineSeries(opts);
      if (!bbLowerRef.current) bbLowerRef.current = chart.addLineSeries(opts);

      const closes = bars.map((b) => b.close);
      const { upper, mid, lower } = calcBB(closes, 20, 2);
      const upperData: { time: UTCTimestamp; value: number }[] = [];
      const midData: { time: UTCTimestamp; value: number }[] = [];
      const lowerData: { time: UTCTimestamp; value: number }[] = [];
      for (let i = 0; i < bars.length; i++) {
        const t = bars[i]!.time as UTCTimestamp;
        if (upper[i] != null) upperData.push({ time: t, value: upper[i] as number });
        if (mid[i] != null) midData.push({ time: t, value: mid[i] as number });
        if (lower[i] != null) lowerData.push({ time: t, value: lower[i] as number });
      }
      bbUpperRef.current.setData(upperData);
      bbMidRef.current.setData(midData);
      bbLowerRef.current.setData(lowerData);
    } else {
      if (bbUpperRef.current) {
        chart.removeSeries(bbUpperRef.current);
        bbUpperRef.current = null;
      }
      if (bbMidRef.current) {
        chart.removeSeries(bbMidRef.current);
        bbMidRef.current = null;
      }
      if (bbLowerRef.current) {
        chart.removeSeries(bbLowerRef.current);
        bbLowerRef.current = null;
      }
    }
  }, [showBB, bars]);

  // Volume overlay
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    if (showVol && bars.length) {
      if (!volRef.current) {
        volRef.current = chart.addHistogramSeries({
          priceScaleId: "volume",
          priceFormat: { type: "volume" },
          priceLineVisible: false,
          lastValueVisible: false,
        });
        chart.priceScale("volume").applyOptions({
          scaleMargins: { top: 0.8, bottom: 0 },
        });
      }
      volRef.current.setData(
        bars.map((b) => ({
          time: b.time as UTCTimestamp,
          value: b.volume,
          color:
            b.close >= b.open ? "rgba(0,200,5,0.5)" : "rgba(255,80,0,0.5)",
        })),
      );
    } else if (volRef.current) {
      chart.removeSeries(volRef.current);
      volRef.current = null;
    }
  }, [showVol, bars]);

  const empty = !isLoading && bars.length === 0;

  return (
    <div className="-mx-6 -my-6 flex flex-col">
      {/* Header bar */}
      <div className="flex h-12 items-center gap-3 border-b border-border bg-surface px-4">
        {/* Symbol combobox */}
        <div ref={comboRef} className="relative">
          <input
            type="text"
            value={comboOpen ? query : symbol}
            placeholder={symbol}
            onFocus={() => {
              setQuery("");
              setComboOpen(true);
            }}
            onChange={(e) => setQuery(e.target.value)}
            className="h-8 w-32 rounded-input border border-border bg-bg px-2 font-mono text-sm text-text-primary outline-none focus:border-text-primary"
          />
          {comboOpen && (
            <div className="absolute left-0 top-9 z-50 max-h-48 w-40 overflow-y-auto rounded-lg border border-border bg-surface shadow-lg">
              {filtered.length === 0 ? (
                <div className="px-3 py-2 text-xs text-text-secondary">
                  No matches
                </div>
              ) : (
                filtered.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onMouseDown={(e) => {
                      e.preventDefault();
                      setSymbol(s);
                      setQuery("");
                      setComboOpen(false);
                    }}
                    className={`flex h-9 w-full items-center px-3 font-mono text-sm hover:bg-bg ${
                      s === symbol ? "text-text-primary" : "text-text-secondary"
                    }`}
                  >
                    {s}
                  </button>
                ))
              )}
            </div>
          )}
        </div>

        {/* Timeframe pills */}
        <div className="flex flex-wrap gap-1.5">
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

        {/* Overlay toggles */}
        <div className="ml-auto flex items-center gap-2">
          <OverlayToggle
            label="EMA 200"
            pressed={showEma}
            onPressedChange={setShowEma}
          />
          <OverlayToggle
            label="Bollinger"
            pressed={showBB}
            onPressedChange={setShowBB}
          />
          <OverlayToggle
            label="Volume"
            pressed={showVol}
            onPressedChange={setShowVol}
          />
        </div>
      </div>

      {/* Chart container */}
      <div
        className="relative w-full"
        style={{ height: "calc(100vh - 168px)" }}
      >
        <div ref={containerRef} className="absolute inset-0" />
        {(isLoading || empty) && (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-bg/50 text-sm text-text-secondary">
            {isLoading ? `Loading ${symbol}…` : `No data for ${symbol}`}
          </div>
        )}
      </div>
    </div>
  );
}

function OverlayToggle({
  label,
  pressed,
  onPressedChange,
}: {
  label: string;
  pressed: boolean;
  onPressedChange: (v: boolean) => void;
}) {
  return (
    <RToggle.Root
      pressed={pressed}
      onPressedChange={onPressedChange}
      className="h-7 rounded-full border border-border bg-transparent px-3 text-xs text-text-secondary transition-colors hover:text-text-primary data-[state=on]:border-text-primary data-[state=on]:bg-text-primary/10 data-[state=on]:text-text-primary"
    >
      {label}
    </RToggle.Root>
  );
}
