import { useEffect } from "react";
import { create } from "zustand";
import { AnimatePresence, motion } from "framer-motion";

export type ToastTone = "success" | "error" | "neutral";

interface ToastEntry {
  id: number;
  message: string;
  tone: ToastTone;
}

interface ToastState {
  toasts: ToastEntry[];
  push: (message: string, tone?: ToastTone) => void;
  dismiss: (id: number) => void;
}

let nextId = 1;

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  push: (message, tone = "neutral") => {
    const id = nextId++;
    set((s) => ({ toasts: [...s.toasts, { id, message, tone }].slice(-3) }));
  },
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));

const TONE_CLASSES: Record<ToastTone, string> = {
  success: "border-bull/30 text-bull",
  error: "border-critical/30 text-critical",
  neutral: "border-border text-text-secondary",
};

function ToastItem({ toast }: { toast: ToastEntry }) {
  const dismiss = useToastStore((s) => s.dismiss);
  useEffect(() => {
    const t = setTimeout(() => dismiss(toast.id), 3000);
    return () => clearTimeout(t);
  }, [toast.id, dismiss]);

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: 32 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 32, transition: { duration: 0.2 } }}
      transition={{ type: "spring", stiffness: 320, damping: 28 }}
      className={`pointer-events-auto min-w-[220px] rounded-card border bg-surface px-4 py-2.5 text-sm shadow-md ${TONE_CLASSES[toast.tone]}`}
    >
      {toast.message}
    </motion.div>
  );
}

export function Toaster() {
  const toasts = useToastStore((s) => s.toasts);
  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      <AnimatePresence initial={false}>
        {toasts.map((t) => (
          <ToastItem key={t.id} toast={t} />
        ))}
      </AnimatePresence>
    </div>
  );
}
