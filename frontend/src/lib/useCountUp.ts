import { useEffect, useRef, useState } from "react";

// Animates toward `target` whenever it changes, starting from wherever the
// previous animation left off -- used for dashboard stats so a refetch's new
// number eases in instead of jumping, without needing a charting library.
export function useCountUp(target: number, durationMs = 500) {
  const [value, setValue] = useState(target);
  const fromRef = useRef(target);

  useEffect(() => {
    const from = fromRef.current;
    if (from === target) return;

    const start = performance.now();
    let frame: number;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / durationMs);
      setValue(from + (target - from) * t);
      if (t < 1) {
        frame = requestAnimationFrame(tick);
      } else {
        fromRef.current = target;
      }
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, durationMs]);

  return value;
}
