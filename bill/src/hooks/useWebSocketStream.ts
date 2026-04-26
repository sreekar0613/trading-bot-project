import { useEffect } from "react";
import { logSocket } from "@/services/websocket";
import { useLogStore } from "@/store/logStore";

export function useWebSocketStream() {
  useEffect(() => {
    logSocket.connect();
    return () => {
      // Singleton stays alive across route changes; do not disconnect on unmount.
    };
  }, []);

  return useLogStore((s) => s.lines);
}
