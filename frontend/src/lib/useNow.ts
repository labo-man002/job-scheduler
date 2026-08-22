import { useEffect, useState } from "react";

// A ticking clock for relative-time labels ("3s ago") that stay live without
// waiting for the next data refetch.
export function useNow(intervalMs = 1000) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);

  return now;
}
