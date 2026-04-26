import throttle from "lodash/throttle";
import { useLogStore } from "@/store/logStore";
import type { LogLine } from "@/types/api";

const WS_URL = import.meta.env.VITE_WS_URL ?? "ws://localhost:8000/ws";
const RECONNECT_DELAY_MS = 2000;
const THROTTLE_MS = 250; // 4 updates / second

class LogSocket {
  private ws: WebSocket | null = null;
  private buffer: LogLine[] = [];
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private manualClose = false;

  private flush = throttle(
    () => {
      if (this.buffer.length === 0) return;
      const drained = this.buffer;
      this.buffer = [];
      useLogStore.getState().pushBatch(drained);
    },
    THROTTLE_MS,
    { leading: false, trailing: true }
  );

  connect() {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }
    this.manualClose = false;
    this.ws = new WebSocket(WS_URL);

    this.ws.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data) as LogLine;
        this.buffer.push(parsed);
        this.flush();
      } catch {
        // Drop malformed frames silently — backend always sends JSON.
      }
    };

    this.ws.onclose = () => {
      if (this.manualClose) return;
      this.scheduleReconnect();
    };

    this.ws.onerror = () => {
      this.ws?.close();
    };
  }

  private scheduleReconnect() {
    if (this.reconnectTimer) return;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, RECONNECT_DELAY_MS);
  }

  disconnect() {
    this.manualClose = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.ws?.close();
    this.ws = null;
  }
}

export const logSocket = new LogSocket();
