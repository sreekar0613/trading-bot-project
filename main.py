import asyncio
import json
import logging
import os
import re
import sqlite3
from collections import deque
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from pathlib import Path

import aiofiles
from dateutil import parser as dateutil_parser
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi import Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt as jose_jwt
import httpx

from utils.alpaca_client import fetch_account, fetch_positions
from utils.database import DB_PATH, get_universe, get_sentiment, get_trades, get_metrics

DASHBOARD_HTML = Path(__file__).resolve().parent / "dashboard.html"
APP_JSX        = Path(__file__).resolve().parent / "app.jsx"

load_dotenv()

AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE", "https://billbot.me/api")
ALLOWED_EMAILS = set(os.getenv("ALLOWED_EMAILS", "skakumani06@gmail.com").split(","))
_jwks_cache: dict = {}

LOG_FILE = Path(__file__).resolve().parent / "logs" / "paper_trading.log"
PORT = int(os.getenv("PORT", 8000))

# Regex matching: "2026-04-23 18:50:22,127 - INFO - message body"
_LOG_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:,\d+)?)"
    r"\s+-\s+(DEBUG|INFO|WARNING|ERROR|CRITICAL)"
    r"\s+-\s+(.+)$"
)
_KNOWN_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

logger = logging.getLogger("trading_api")


# ---------------------------------------------------------------------------
# Auth0 JWT verification
# ---------------------------------------------------------------------------

async def _get_jwks() -> dict:
    global _jwks_cache
    if _jwks_cache:
        return _jwks_cache
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"https://{AUTH0_DOMAIN}/.well-known/jwks.json")
        resp.raise_for_status()
        _jwks_cache = resp.json()
    return _jwks_cache

async def verify_token(token: str) -> dict:
    try:
        jwks = await _get_jwks()
        header = jose_jwt.get_unverified_header(token)
        key = next(
            (k for k in jwks["keys"] if k["kid"] == header["kid"]),
            None,
        )
        if key is None:
            raise HTTPException(status_code=401, detail="Unknown signing key")
        payload = jose_jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=AUTH0_AUDIENCE,
            issuer=f"https://{AUTH0_DOMAIN}/",
        )
        email = payload.get("email") or payload.get("https://billbot.me/email")
        if email not in ALLOWED_EMAILS:
            raise HTTPException(status_code=403, detail="Email not authorized")
        return payload
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

_bearer = HTTPBearer()

async def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    return await verify_token(credentials.credentials)


# ---------------------------------------------------------------------------
# Connection manager
# ---------------------------------------------------------------------------

class ConnectionManager:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._clients.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._clients.discard(ws)

    async def broadcast(self, payload: dict) -> None:
        if not self._clients:
            return
        text = json.dumps(payload)
        results = await asyncio.gather(
            *[client.send_text(text) for client in list(self._clients)],
            return_exceptions=True,
        )
        # Drop any clients that failed
        for client, result in zip(list(self._clients), results):
            if isinstance(result, Exception):
                self.disconnect(client)


manager = ConnectionManager()


# ---------------------------------------------------------------------------
# Log line parser
# ---------------------------------------------------------------------------

def parse_log_line(raw: str) -> dict:
    """Return a structured dict for one raw log line."""
    raw = raw.rstrip("\n")
    m = _LOG_RE.match(raw)
    if m:
        ts_str, level, message = m.group(1), m.group(2), m.group(3)
        # Normalise comma-millisecond to dot so it's valid ISO-ish
        ts_normalised = ts_str.replace(",", ".")
        return {"type": "log", "timestamp": ts_normalised, "level": level, "message": message}
    # Unparseable line — still surface it
    return {"type": "log", "timestamp": datetime.now(timezone.utc).isoformat(), "level": "INFO", "message": raw}


def read_tail(path: Path, n: int = 100) -> list[dict]:
    """Return the last n parsed lines from path (synchronous, called once on connect)."""
    if not path.exists():
        return []
    with open(path, "r") as f:
        lines = deque(f, maxlen=n)
    return [parse_log_line(line) for line in lines if line.strip()]


# ---------------------------------------------------------------------------
# Background file-watcher task
# ---------------------------------------------------------------------------

async def _tail_log_file() -> None:
    """Tail LOG_FILE forever, broadcasting new lines to all connected clients."""
    # Wait until the file exists before starting
    while not LOG_FILE.exists():
        await asyncio.sleep(2)

    async with aiofiles.open(LOG_FILE, "r") as f:
        await f.seek(0, 2)          # start at end of file
        while True:
            line = await f.readline()
            if line:
                if line.strip():
                    await manager.broadcast(parse_log_line(line))
            else:
                await asyncio.sleep(1)


# ---------------------------------------------------------------------------
# App lifespan: start background watcher once on startup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_tail_log_file())
    yield
    task.cancel()


app = FastAPI(title="Trading Bot API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://billbot.me", "http://localhost:5173"],   # dashboard served from same host; also allows file:// dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def dashboard():
    if not DASHBOARD_HTML.exists():
        raise HTTPException(status_code=404, detail="dashboard.html not found")
    return FileResponse(DASHBOARD_HTML, media_type="text/html")


@app.get("/app.jsx")
def serve_jsx():
    if not APP_JSX.exists():
        raise HTTPException(status_code=404, detail="app.jsx not found")
    return FileResponse(APP_JSX, media_type="application/javascript")


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def websocket_logs(ws: WebSocket, token: str = Query(default="")) -> None:
    try:
        await verify_token(token)
    except HTTPException:
        await ws.close(code=1008)
        return
    await manager.connect(ws)
    try:
        # Send last 100 lines immediately on connect
        if not LOG_FILE.exists():
            await ws.send_text(json.dumps({"type": "error", "message": "Log file not found"}))
        else:
            try:
                history = read_tail(LOG_FILE, n=100)
                for entry in history:
                    await ws.send_text(json.dumps(entry))
            except Exception as exc:
                await ws.send_text(json.dumps({"type": "error", "message": f"Failed to read logs: {exc}"}))

        # Keep the connection alive; background task handles new-line broadcasts
        while True:
            await ws.receive_text()   # will raise WebSocketDisconnect on close

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("WebSocket error: %s", exc)
    finally:
        manager.disconnect(ws)


# ---------------------------------------------------------------------------
# REST endpoints (unchanged)
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/api/account")
def account(_: dict = Depends(require_auth)):
    try:
        return fetch_account()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/universe")
def universe(_: dict = Depends(require_auth)):
    try:
        data = get_universe()
        if not data:
            raise HTTPException(status_code=404, detail="No universe data found")
        return data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sentiment")
def sentiment(_: dict = Depends(require_auth)):
    try:
        data = get_sentiment()
        if not data:
            raise HTTPException(status_code=404, detail="No sentiment data found")
        return data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/positions")
def positions(_: dict = Depends(require_auth)):
    try:
        return fetch_positions()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/trades")
def trades(_: dict = Depends(require_auth)):
    try:
        data = get_trades(limit=50)
        if not data:
            raise HTTPException(status_code=404, detail="No trade log found")
        return data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/metrics")
def metrics(_: dict = Depends(require_auth)):
    try:
        data = get_metrics()
        if not data:
            raise HTTPException(status_code=404, detail="No backtest results found")
        return data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Bot Control Endpoints (Task #7)
# ---------------------------------------------------------------------------

@app.post("/api/bot/pause")
def pause_bot(_: dict = Depends(require_auth)):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("UPDATE portfolio_state SET paused = 1 WHERE id = 1")
        return {"status": "paused"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/bot/resume")
def resume_bot(_: dict = Depends(require_auth)):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("UPDATE portfolio_state SET paused = 0 WHERE id = 1")
        return {"status": "resumed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/bot/status")
def bot_status_endpoint():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            try:
                row = conn.execute(
                    "SELECT paused, last_heartbeat, open_position_count, current_regime FROM portfolio_state WHERE id = 1"
                ).fetchone()
            except sqlite3.OperationalError:
                row = conn.execute(
                    "SELECT paused, last_heartbeat, open_position_count FROM portfolio_state WHERE id = 1"
                ).fetchone()
            if row:
                return {
                    "paused": bool(row[0]),
                    "last_heartbeat": row[1],
                    "open_position_count": row[2],
                    "current_regime": row[3] if len(row) > 3 else None
                }
            return {"paused": False, "last_heartbeat": None, "open_position_count": 0, "current_regime": None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Sidecar context aggregator (loopback only — no auth)
# ---------------------------------------------------------------------------

def _safe(fn, *args, **kwargs):
    """Run fn, returning its result or {'error': str(exc)} on failure."""
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        return {"error": str(exc)}


def _bot_status() -> dict:
    """Read halted_until from portfolio_state and derive last_updated from log mtime.

    Also query paused, last_heartbeat, and open_position_count for the sidecar context.
    """
    halted = False
    paused = False
    last_heartbeat = None
    open_position_count = 0
    current_regime = None
    try:
        with sqlite3.connect(DB_PATH) as conn:
            try:
                row = conn.execute(
                    "SELECT halted_until, paused, last_heartbeat, open_position_count, current_regime FROM portfolio_state WHERE id = 1"
                ).fetchone()
            except sqlite3.OperationalError:
                row = conn.execute(
                    "SELECT halted_until, paused, last_heartbeat, open_position_count FROM portfolio_state WHERE id = 1"
                ).fetchone()
        if row:
            halted_until_raw = row[0]
            if halted_until_raw:
                if "T" in halted_until_raw:
                    try:
                        halted_until_dt = dateutil_parser.parse(halted_until_raw)
                        if halted_until_dt.date() >= date.today():
                            halted = True
                    except (ValueError, TypeError):
                        pass
                elif halted_until_raw == date.today().isoformat():
                    halted = True
            paused = bool(row[1])
            last_heartbeat = row[2]
            open_position_count = row[3]
            if len(row) > 4:
                current_regime = row[4]
    except Exception:
        pass

    last_updated = None
    if LOG_FILE.exists():
        last_updated = datetime.fromtimestamp(
            LOG_FILE.stat().st_mtime, tz=timezone.utc
        ).isoformat()

    return {
        "halted": halted,
        "paused": paused,
        "last_heartbeat": last_heartbeat,
        "open_position_count": open_position_count,
        "current_regime": current_regime,
        "last_updated": last_updated
    }


_TIMEFRAME_LOOKBACK = {"1D": 1, "1W": 7, "1M": 30, "3M": 90, "6M": 180, "1Y": 365}


@app.get("/api/history/{symbol}")
def history(symbol: str, timeframe: str = "1D", _: dict = Depends(require_auth)):
    try:
        sym = symbol.upper()
        days = _TIMEFRAME_LOOKBACK.get(timeframe)
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            if days is None:
                rows = conn.execute(
                    "SELECT date, open, high, low, close, volume FROM price_history "
                    "WHERE symbol = ? ORDER BY date ASC",
                    (sym,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT date, open, high, low, close, volume FROM price_history "
                    "WHERE symbol = ? AND date >= date("
                    "(SELECT MAX(date) FROM price_history WHERE symbol = ?), ?"
                    ") ORDER BY date ASC",
                    (sym, sym, f"-{days} days"),
                ).fetchall()

        bars = [
            {
                "time": int(datetime.strptime(row["date"], "%Y-%m-%d").timestamp()),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": int(row["volume"]) if row["volume"] is not None else 0,
            }
            for row in rows
        ]
        return {"bars": bars}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sidecar/context")
def sidecar_context(_: dict = Depends(require_auth)):
    trades_data = _safe(get_trades, limit=10)
    return {
        "account": _safe(fetch_account),
        "positions": _safe(fetch_positions),
        "metrics": _safe(get_metrics),
        "trades": trades_data,
        "bot_status": _bot_status(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
