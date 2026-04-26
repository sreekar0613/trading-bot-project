import { useEffect, useRef, useState } from "react";
import { motion, useMotionValue, useTransform, animate } from "framer-motion";
import { ChevronsRight, Loader2 } from "lucide-react";

interface SlideToConfirmProps {
  label: string;
  onConfirm: () => void | Promise<void>;
  loading?: boolean;
  disabled?: boolean;
}

const TRACK_HEIGHT = 48;
const THUMB_SIZE = 40;

export function SlideToConfirm({ label, onConfirm, loading, disabled }: SlideToConfirmProps) {
  const trackRef = useRef<HTMLDivElement | null>(null);
  const [trackWidth, setTrackWidth] = useState(0);
  const [confirmed, setConfirmed] = useState(false);
  const x = useMotionValue(0);

  useEffect(() => {
    if (!trackRef.current) return;
    const ro = new ResizeObserver(() => {
      if (trackRef.current) setTrackWidth(trackRef.current.clientWidth);
    });
    ro.observe(trackRef.current);
    setTrackWidth(trackRef.current.clientWidth);
    return () => ro.disconnect();
  }, []);

  const maxDrag = Math.max(0, trackWidth - THUMB_SIZE - 4);
  const labelOpacity = useTransform(x, [0, maxDrag * 0.6], [1, 0]);

  async function handleEnd() {
    if (confirmed || loading || disabled) return;
    if (x.get() >= maxDrag - 4) {
      setConfirmed(true);
      animate(x, maxDrag, { duration: 0.15 });
      try {
        await onConfirm();
      } catch {
        animate(x, 0, { duration: 0.25 });
        setConfirmed(false);
      }
    } else {
      animate(x, 0, { duration: 0.2 });
    }
  }

  const isBusy = loading || confirmed;

  return (
    <div
      ref={trackRef}
      className="relative w-full overflow-hidden rounded-full border border-border bg-bg select-none"
      style={{ height: TRACK_HEIGHT }}
    >
      <motion.div
        className="pointer-events-none absolute inset-0 flex items-center justify-center text-sm text-text-secondary"
        style={{ opacity: labelOpacity }}
      >
        {label}
      </motion.div>

      <motion.div
        drag={isBusy || disabled ? false : "x"}
        dragConstraints={{ left: 0, right: maxDrag }}
        dragElastic={0}
        dragMomentum={false}
        onDragEnd={handleEnd}
        style={{ x, width: THUMB_SIZE, height: THUMB_SIZE }}
        className="absolute left-[2px] top-[2px] flex cursor-grab items-center justify-center rounded-full bg-critical text-white shadow-sm active:cursor-grabbing"
      >
        {isBusy ? <Loader2 size={18} className="animate-spin" /> : <ChevronsRight size={18} />}
      </motion.div>
    </div>
  );
}
