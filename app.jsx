const { useState, useEffect, useRef, useMemo, useCallback } = React;

// ─── Bootstrap & config ───────────────────────────────────────────────────────
const INITIAL  = JSON.parse(document.getElementById('initial-data').textContent);
const WS_URL   = () => `ws://${window.location.host}/ws`;
const POLL_MS  = 3000;
const MAX_LOGS = 300;
const SPARK_N  = 50;

// Seed a smooth sparkline history from a base value
function seedSparkline(base, n, volatility, drift) {
  const pts = [];
  let v = base * (1 - volatility * n * 0.5);
  for (let i = 0; i < n; i++) {
    v += (Math.random() - drift) * base * volatility;
    pts.push(v);
  }
  pts.push(base);
  return pts;
}

function nowET() {
  return new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

// ─── formatUSD (unchanged from design) ───────────────────────────────────────
function formatUSD(v) {
  const [dollars, cents] = v.toFixed(2).split('.');
  const withCommas = Number(dollars).toLocaleString('en-US');
  return { dollars: withCommas, cents };
}

// ─── Sparkline (unchanged from design) ───────────────────────────────────────
function Sparkline({ data, color = '#0a0b0d', width = 300, height = 56 }) {
  if (!data || data.length < 2) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const step = width / (data.length - 1);
  const pts = data.map((v, i) => `${i * step},${height - ((v - min) / range) * (height - 6) - 3}`);
  const d = 'M' + pts.join(' L');
  const area = d + ` L${width},${height} L0,${height} Z`;
  return (
    <svg className="spark" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
      <defs>
        <linearGradient id={`g-${color.replace('#','')}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"   stopColor={color} stopOpacity="0.12" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#g-${color.replace('#','')})`} />
      <path d={d} fill="none" stroke={color} strokeWidth="1.25" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

// ─── KpiCard (unchanged from design) ─────────────────────────────────────────
function KpiCard({ label, tag, value, previous, sub, spark, sparkColor, delay }) {
  const { dollars, cents } = formatUSD(value);
  const delta = previous != null ? ((value - previous) / previous) * 100 : 0;
  const isPos = delta >= 0;
  return (
    <div className={`kpi-card fade-up delay-${delay}`}>
      {spark && <Sparkline data={spark} color={sparkColor} />}
      <div className="kpi-label">
        <span>{label}</span>
        <span className="kpi-label-tag">{tag}</span>
      </div>
      <div className="kpi-value tnum">
        <span className="currency">USD</span>{dollars}<span className="cents">.{cents}</span>
      </div>
      <div className="kpi-foot">
        <span>{sub}</span>
        {previous != null && (
          <span className={`kpi-delta ${isPos ? 'pos' : 'neg'}`}>
            <span className="arrow">{isPos ? '▲' : '▼'}</span>
            {isPos ? '+' : ''}{delta.toFixed(2)}%
          </span>
        )}
      </div>
    </div>
  );
}

// ─── SentimentCell (unchanged from design) ────────────────────────────────────
function SentimentCell({ score }) {
  const cls   = score > 0.015 ? 'pos' : score < -0.015 ? 'neg' : 'neu';
  const arrow = cls === 'pos' ? '▲' : cls === 'neg' ? '▼' : '◆';
  const sign  = score >= 0 ? '+' : '';
  return (
    <span className={`sentiment ${cls}`}>
      <span className="arrow">{arrow}</span>
      {sign}{score.toFixed(3)}
    </span>
  );
}

// ─── BuzzCell (unchanged from design) ────────────────────────────────────────
function BuzzCell({ buzz, max }) {
  const pct = Math.min(100, (buzz / max) * 100);
  return (
    <div className="buzz-cell">
      <div className="buzz-bar"><div className="buzz-bar-fill" style={{ width: `${pct}%` }} /></div>
      <span className="buzz-count">{buzz}</span>
    </div>
  );
}

// ─── signalFor (unchanged from design) ───────────────────────────────────────
function signalFor(score, buzz) {
  if (score > 0.15 && buzz >= 10) return 'buy';
  if (score < -0.15 && buzz >= 10) return 'sell';
  return 'hold';
}

// ─── UniverseTable (unchanged from design) ───────────────────────────────────
function UniverseTable({ data, filter, setFilter, search, setSearch }) {
  const [sort, setSort]       = useState({ key: 'sentiment_score', dir: 'desc' });
  const [selected, setSelected] = useState(null);
  const maxBuzz = useMemo(() => Math.max(...data.map(d => d.buzz || 0), 1), [data]);

  const sectors = useMemo(() => {
    const counts = {};
    data.forEach(d => { counts[d.sector] = (counts[d.sector] || 0) + 1; });
    return Object.entries(counts).sort((a, b) => b[1] - a[1]);
  }, [data]);

  const processed = useMemo(() => {
    let rows = data;
    if (filter !== 'all') rows = rows.filter(r => r.sector === filter);
    if (search.trim()) {
      const q = search.toLowerCase();
      rows = rows.filter(r =>
        r.ticker.toLowerCase().includes(q) || r.sector.toLowerCase().includes(q)
      );
    }
    return [...rows].sort((a, b) => {
      const { key, dir } = sort;
      let av = a[key], bv = b[key];
      if (typeof av === 'string') { av = av.toLowerCase(); bv = bv.toLowerCase(); }
      if (av < bv) return dir === 'asc' ? -1 : 1;
      if (av > bv) return dir === 'asc' ? 1 : -1;
      return 0;
    });
  }, [data, filter, search, sort]);

  const onSort   = (key) => setSort(s => s.key === key ? { key, dir: s.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: 'desc' });
  const sortIcon = (key) => sort.key !== key ? '↕' : sort.dir === 'asc' ? '↑' : '↓';

  return (
    <div>
      <div className="toolbar">
        <button className={`chip ${filter === 'all' ? 'active' : ''}`} onClick={() => setFilter('all')}>
          All<span className="c-count">{data.length}</span>
        </button>
        {sectors.map(([sector, count]) => (
          <button
            key={sector}
            className={`chip ${filter === sector ? 'active' : ''}`}
            onClick={() => setFilter(sector)}
          >
            {sector}<span className="c-count">{count}</span>
          </button>
        ))}
        <div className="search">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#6b7079" strokeWidth="2">
            <circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" />
          </svg>
          <input
            placeholder="Filter ticker or sector…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
          <span className="kbd">⌘K</span>
        </div>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th onClick={() => onSort('ticker')}  className={sort.key === 'ticker'  ? 'active' : ''}>
                Ticker <span className="sort">{sortIcon('ticker')}</span>
              </th>
              <th onClick={() => onSort('sector')}  className={sort.key === 'sector'  ? 'active' : ''}>
                Sector <span className="sort">{sortIcon('sector')}</span>
              </th>
              <th className={`num ${sort.key === 'sentiment_score' ? 'active' : ''}`} onClick={() => onSort('sentiment_score')}>
                Sentiment Score <span className="sort">{sortIcon('sentiment_score')}</span>
              </th>
              <th className={`num ${sort.key === 'buzz' ? 'active' : ''}`} onClick={() => onSort('buzz')}>
                Buzz <span className="sort">{sortIcon('buzz')}</span>
              </th>
              <th className="num">Signal</th>
            </tr>
          </thead>
          <tbody>
            {processed.length === 0 && (
              <tr className="empty-row"><td colSpan="5">No tickers match the current filter.</td></tr>
            )}
            {processed.map((row) => {
              const sig = signalFor(row.sentiment_score, row.buzz);
              return (
                <tr
                  key={row.ticker}
                  className={selected === row.ticker ? 'selected' : ''}
                  onClick={() => setSelected(s => s === row.ticker ? null : row.ticker)}
                >
                  <td>
                    <div className="ticker-cell">
                      <div className="ticker-mark">{row.ticker.slice(0, 2)}</div>
                      <span className="ticker-sym">{row.ticker}</span>
                    </div>
                  </td>
                  <td className="sector">{row.sector}</td>
                  <td className="num"><SentimentCell score={row.sentiment_score} /></td>
                  <td className="num"><BuzzCell buzz={row.buzz} max={maxBuzz} /></td>
                  <td className="num">
                    <div className="signal-cell">
                      <span className={`signal-label ${sig}`}>{sig}</span>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── HighlightedMsg (unchanged from design, extended for real symbols) ────────
// Symbols are set dynamically from the universe once loaded
let KNOWN_SYMBOLS = new Set(['AAPL','NVDA','TSLA','META','GOOGL','AMD','BA','LLY','MSFT','AMZN','NFLX','GE','JPM','MSFT','INTC','BAC','GS','XOM','CVX']);

function HighlightedMsg({ msg }) {
  const parts = msg.split(/(\s+|→|\$[0-9.,+\-]+|[A-Z]{2,6}\b|[0-9]+\.[0-9]+|\+[0-9.]+|-[0-9.]+|\[paper\])/g).filter(Boolean);
  return (
    <>
      {parts.map((p, i) => {
        if (/^→$/.test(p))                              return <span key={i} className="tok-arrow">{p}</span>;
        if (/^[A-Z]{2,6}$/.test(p) && KNOWN_SYMBOLS.has(p)) return <span key={i} className="tok-ticker">{p}</span>;
        if (/^\$[0-9.,+\-]+$/.test(p))                  return <span key={i} className="tok-str">{p}</span>;
        if (/^\+[0-9.]+$/.test(p))                       return <span key={i} className="tok-pos">{p}</span>;
        if (/^-[0-9.]+$/.test(p))                        return <span key={i} className="tok-neg">{p}</span>;
        if (/^[0-9]+\.[0-9]+$/.test(p))                  return <span key={i} className="tok-num">{p}</span>;
        if (/^\[paper\]$/.test(p))                        return <span key={i} className="tok-str">{p}</span>;
        return <span key={i}>{p}</span>;
      })}
    </>
  );
}

// ─── Terminal ─────────────────────────────────────────────────────────────────
// Accepts lines + connStatus as props; manages autoscroll & clear internally.
function Terminal({ lines, onClear, running, setRunning, connStatus }) {
  const [autoscroll, setAutoscroll] = useState(true);
  const bodyRef = useRef(null);

  useEffect(() => {
    if (autoscroll && bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    }
  }, [lines, autoscroll]);

  const counts = useMemo(() => {
    const c = { INFO: 0, WARN: 0, WARNING: 0, ERROR: 0, CRITICAL: 0, DEBUG: 0 };
    lines.forEach(l => { c[l.level] = (c[l.level] || 0) + 1; });
    return {
      INFO:  c.INFO,
      WARN:  c.WARN + c.WARNING,
      ERROR: c.ERROR + c.CRITICAL,
      DEBUG: c.DEBUG,
    };
  }, [lines]);

  // Map real log levels to CSS class names matching the design
  const levelCls = (lvl) => {
    const m = { WARNING: 'warn', CRITICAL: 'error' };
    return m[lvl] ?? lvl.toLowerCase();
  };

  // ws status button label
  const wsLabel = connStatus === 'live' ? '● ws:live' : connStatus === 'connecting' ? '◌ ws:conn' : '○ ws:off';

  return (
    <div className="terminal fade-up delay-4">
      <div className="terminal-chrome">
        <div className="tlights">
          <div className="tlight r" />
          <div className="tlight y" />
          <div className="tlight g" />
        </div>
        <div className="terminal-title">
          <span className="path">~/sentio/logs/</span>paper_trading.log <span style={{ color: '#3a3d44' }}>—</span> tail -f
        </div>
        <div className="terminal-actions">
          <button className="t-btn" onClick={() => setAutoscroll(a => !a)} title="Toggle autoscroll">
            {autoscroll ? 'autoscroll ✓' : 'autoscroll'}
          </button>
          <button className="t-btn" style={{ color: connStatus === 'live' ? 'oklch(0.75 0.16 150)' : '#6b7079' }}>
            {wsLabel}
          </button>
          <button className="t-btn" onClick={onClear}>clear</button>
          <button
            className={`t-btn ${running ? 'live' : ''}`}
            onClick={() => setRunning(r => !r)}
          >{running ? 'live' : 'paused'}</button>
        </div>
      </div>

      <div
        className="terminal-body"
        ref={bodyRef}
        onWheel={() => setAutoscroll(false)}
        onClick={() => setAutoscroll(true)}
      >
        {lines.length === 0 && (
          <div style={{ color: '#6b7079' }}>Connecting to log stream…</div>
        )}
        {lines.map(l => (
          <div className="log-line" key={l.id}>
            <span className="log-time">{l.ts}</span>
            <span className={`log-level ${levelCls(l.level)}`}>{l.level}</span>
            <span className="log-msg"><HighlightedMsg msg={l.msg} /></span>
          </div>
        ))}
        <div className="prompt-line">
          <span className="ps">❯</span>
          <span className="cwd">sentio@paper</span>
          <span>tail -f paper_trading.log</span>
          <span className="caret" />
        </div>
      </div>

      <div className="terminal-footer">
        <div className="stats">
          <div className="stat">lines <b>{lines.length}</b></div>
          <div className="stat">info  <b>{counts.INFO}</b></div>
          <div className="stat">warn  <b>{counts.WARN}</b></div>
          <div className="stat">error <b>{counts.ERROR}</b></div>
          <div className="stat">debug <b>{counts.DEBUG}</b></div>
        </div>
        <div>utf-8 · LF · python 3.13 · pid auto</div>
      </div>
    </div>
  );
}

// ─── App ──────────────────────────────────────────────────────────────────────
function App() {
  // ── Account state ──────────────────────────────────────────────────────────
  const [equity,     setEquity]     = useState(INITIAL.portfolio_equity);
  const [buyPower,   setBuyPower]   = useState(INITIAL.buying_power);
  const [prevEquity, setPrevEquity] = useState(INITIAL.portfolio_equity);
  const [prevBP,     setPrevBP]     = useState(INITIAL.buying_power);
  const [equityHist, setEquityHist] = useState(() => seedSparkline(INITIAL.portfolio_equity, SPARK_N, 0.003, 0.48));
  const [bpHist,     setBpHist]     = useState(() => seedSparkline(INITIAL.buying_power,     SPARK_N, 0.002, 0.50));

  // ── Universe state ─────────────────────────────────────────────────────────
  const [universe, setUniverse] = useState(INITIAL.fundamental_universe);
  const [filter,   setFilter]   = useState('all');
  const [search,   setSearch]   = useState('');

  // ── Terminal state ─────────────────────────────────────────────────────────
  const [termLines,  setTermLines]  = useState([]);
  const [running,    setRunning]    = useState(true);
  const [connStatus, setConnStatus] = useState('connecting');

  // ── Clock ──────────────────────────────────────────────────────────────────
  const [timeStr, setTimeStr] = useState(nowET());
  useEffect(() => {
    const t = setInterval(() => setTimeStr(nowET()), 1000);
    return () => clearInterval(t);
  }, []);

  // Refs needed by stable WS callbacks
  const wsRef      = useRef(null);
  const runningRef = useRef(true);
  useEffect(() => { runningRef.current = running; }, [running]);

  // ── REST polling ───────────────────────────────────────────────────────────
  const fetchAll = useCallback(async () => {
    try {
      const [acctR, uniR, sentR] = await Promise.all([
        fetch('/api/account').then(r => r.ok ? r.json() : null).catch(() => null),
        fetch('/api/universe').then(r => r.ok ? r.json() : null).catch(() => null),
        fetch('/api/sentiment').then(r => r.ok ? r.json() : null).catch(() => null),
      ]);

      if (acctR) {
        setPrevEquity(equity);
        setPrevBP(buyPower);
        setEquity(acctR.equity);
        setBuyPower(acctR.buying_power);
        setEquityHist(h => { const n = [...h, acctR.equity]; return n.length > SPARK_N ? n.slice(-SPARK_N) : n; });
        setBpHist(h =>     { const n = [...h, acctR.buying_power]; return n.length > SPARK_N ? n.slice(-SPARK_N) : n; });
      }

      if (uniR && sentR) {
        // Build sentiment lookup by symbol
        const sentMap = {};
        sentR.forEach(s => { sentMap[s.symbol] = s; });

        // Update KNOWN_SYMBOLS for the HighlightedMsg highlighter
        uniR.forEach(u => KNOWN_SYMBOLS.add(u.symbol));

        setUniverse(uniR.map(u => ({
          ticker:          u.symbol,
          sector:          u.sector ?? '—',
          sentiment_score: sentMap[u.symbol]?.sentiment_score ?? 0,
          buzz:            Math.round(Math.abs(sentMap[u.symbol]?.buzz_ratio ?? 0)),
        })));
      } else if (uniR) {
        uniR.forEach(u => KNOWN_SYMBOLS.add(u.symbol));
        setUniverse(uniR.map(u => ({
          ticker: u.symbol, sector: u.sector ?? '—', sentiment_score: 0, buzz: 0,
        })));
      }
    } catch (e) {
      console.warn('[API] fetchAll error:', e);
    }
  }, [equity, buyPower]);

  useEffect(() => {
    fetchAll();
    const t = setInterval(fetchAll, POLL_MS);
    return () => clearInterval(t);
  }, [fetchAll]);

  // ── WebSocket ──────────────────────────────────────────────────────────────
  const connectWs = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState < 2) return;

    setConnStatus('connecting');
    const ws = new WebSocket(WS_URL());
    wsRef.current = ws;

    ws.onopen = () => setConnStatus('live');

    ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data);
        if (data.type === 'log' || data.type === 'error') {
          const ts  = (data.timestamp || new Date().toISOString()).replace('T', ' ').slice(0, 23);
          const line = { id: Math.random().toString(36).slice(2), ts, level: data.level || 'INFO', msg: data.message || '' };
          setTermLines(prev => { const n = [...prev, line]; return n.length > MAX_LOGS ? n.slice(-MAX_LOGS) : n; });
        }
      } catch { /* ignore parse errors */ }
    };

    ws.onerror = () => setConnStatus('disconnected');

    ws.onclose = () => {
      if (!runningRef.current) { setConnStatus('paused'); return; }
      setConnStatus('disconnected');
      setTermLines(prev => [...prev, {
        id: Math.random().toString(36).slice(2),
        ts: new Date().toISOString().replace('T', ' ').slice(0, 23),
        level: 'WARNING',
        msg: 'Log stream disconnected — reconnecting in 5 s',
      }]);
      setTimeout(() => { if (runningRef.current) connectWs(); }, 5000);
    };
  }, []); // stable — uses runningRef, not state

  // Pause / resume WebSocket when terminal toggle changes
  useEffect(() => {
    if (running) {
      connectWs();
    } else {
      if (wsRef.current) {
        wsRef.current.onclose = null;   // don't auto-reconnect
        wsRef.current.close();
        wsRef.current = null;
      }
      setConnStatus('paused');
      setTermLines(prev => [...prev, {
        id: Math.random().toString(36).slice(2),
        ts: new Date().toISOString().replace('T', ' ').slice(0, 23),
        level: 'INFO',
        msg: 'Log stream paused by user',
      }]);
    }
    return () => {
      if (wsRef.current) { wsRef.current.onclose = null; wsRef.current.close(); }
    };
  }, [running, connectWs]);

  // ── Render ────────────────────────────────────────────────────────────────
  const bpRatio = (buyPower / equity).toFixed(2);

  // status dot class based on ws connection
  const dotCls = connStatus === 'live' ? '' : connStatus === 'paused' ? 'warn' : 'err';

  return (
    <div className="app">
      {/* ── Header ── */}
      <header className="header fade-up">
        <div className="brand">
          <div className="brand-mark">S</div>
          <div>
            <div className="brand-name">Sentio <span style={{ color: 'var(--ink-4)', fontWeight: 400 }}>/ paper</span></div>
          </div>
          <span className="brand-sub">v2.1.4</span>
        </div>
        <div className="header-meta">
          <div className="meta-item">
            <span className={`status-dot ${dotCls}`} />
            <span>{connStatus === 'live' ? 'Bot running' : connStatus}</span>
          </div>
          <div className="meta-item">
            <span>Strategy</span>
            <span className="mono">sentiment_momentum</span>
          </div>
          <div className="meta-item">
            <span>Market</span>
            <span className="mono">NYSE · paper</span>
          </div>
          <div className="meta-item">
            <span className="mono" id="clock">{timeStr} ET</span>
          </div>
        </div>
      </header>

      {/* ── KPI cards ── */}
      <div className="kpi-row">
        <KpiCard
          label="Account Equity"
          tag="realtime"
          value={equity}
          previous={prevEquity !== equity ? prevEquity : null}
          sub="Settled + unrealized · paper"
          spark={equityHist}
          sparkColor="#0a0b0d"
          delay={1}
        />
        <KpiCard
          label="Buying Power"
          tag="2× margin"
          value={buyPower}
          previous={prevBP !== buyPower ? prevBP : null}
          sub={`${bpRatio}× equity available`}
          spark={bpHist}
          sparkColor="#0052ff"
          delay={2}
        />
      </div>

      {/* ── Universe table ── */}
      <div className="section fade-up delay-3">
        <div className="section-head">
          <div className="section-title">
            Fundamental Universe
            <span className="count">{universe.length} tickers</span>
          </div>
          <div className="section-sub">updated · scan 4:05pm ET</div>
        </div>
        <UniverseTable
          data={universe}
          filter={filter}
          setFilter={setFilter}
          search={search}
          setSearch={setSearch}
        />
      </div>

      {/* ── Terminal ── */}
      <div className="section">
        <div className="section-head">
          <div className="section-title">
            Execution Log
            <span className="count">paper_trading.log</span>
          </div>
          <div className="section-sub">streaming · tail -f</div>
        </div>
        <Terminal
          lines={termLines}
          onClear={() => setTermLines([])}
          running={running}
          setRunning={setRunning}
          connStatus={connStatus}
        />
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
