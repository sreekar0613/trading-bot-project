import asyncio
import json
import logging
import os
import re
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import aiofiles
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from utils.alpaca_client import fetch_account, fetch_positions
from utils.database import get_universe, get_sentiment, get_trades, get_metrics

DASHBOARD_HTML = Path(__file__).resolve().parent / "dashboard.html"
APP_JSX        = Path(__file__).resolve().parent / "app.jsx"

load_dotenv()

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
    allow_origins=["*"],   # dashboard served from same host; also allows file:// dev
    allow_credentials=False,
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
async def websocket_logs(ws: WebSocket) -> None:
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
def account():
    try:
        return fetch_account()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/universe")
def universe():
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
def sentiment():
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
def positions():
    try:
        return fetch_positions()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/trades")
def trades():
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
def metrics():
    try:
        data = get_metrics()
        if not data:
            raise HTTPException(status_code=404, detail="No backtest results found")
        return data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
