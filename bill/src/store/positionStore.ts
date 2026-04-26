import { create } from "zustand";
import type { PositionPayload } from "@/types/api";

// Optional WS overlay. When the backend starts pushing position frames,
// the websocket layer can call `setAll` / `upsert` to keep this fresh.
// Components read from here first; if empty, they fall back to TanStack Query data.
interface PositionStore {
  bySymbol: Record<string, PositionPayload>;
  setAll: (positions: PositionPayload[]) => void;
  upsert: (position: PositionPayload) => void;
  clear: () => void;
}

export const usePositionStore = create<PositionStore>((set) => ({
  bySymbol: {},
  setAll: (positions) =>
    set({
      bySymbol: Object.fromEntries(positions.map((p) => [p.symbol, p])),
    }),
  upsert: (position) =>
    set((state) => ({
      bySymbol: { ...state.bySymbol, [position.symbol]: position },
    })),
  clear: () => set({ bySymbol: {} }),
}));
