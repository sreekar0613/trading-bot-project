import { create } from "zustand";
import type { LogLine } from "@/types/api";

const MAX_LINES = 1000;

interface LogStore {
  lines: LogLine[];
  push: (line: LogLine) => void;
  pushBatch: (batch: LogLine[]) => void;
  clear: () => void;
}

export const useLogStore = create<LogStore>((set) => ({
  lines: [],
  push: (line) =>
    set((state) => {
      const next = [...state.lines, line];
      if (next.length > MAX_LINES) next.splice(0, next.length - MAX_LINES);
      return { lines: next };
    }),
  pushBatch: (batch) =>
    set((state) => {
      const next = [...state.lines, ...batch];
      if (next.length > MAX_LINES) next.splice(0, next.length - MAX_LINES);
      return { lines: next };
    }),
  clear: () => set({ lines: [] }),
}));
