"use client";

import { useEffect, useState } from "react";

/**
 * Tracks how many seconds remain until the next auto-refetch and returns
 * the 0-to-1 progress (1 = just refreshed, 0 = due now).
 *
 * @param dataUpdatedAt  `dataUpdatedAt` from `useQuery` (epoch ms; 0 before first fetch)
 * @param intervalMs     The `refetchInterval` passed to the same query
 */
export function useRefreshCountdown(dataUpdatedAt: number, intervalMs: number) {
  // Store current epoch-ms as state updated by a 1-second interval.
  // This avoids calling the impure Date.now() directly during render
  // (which would violate the react-hooks/purity rule), while still keeping
  // the countdown accurate to ±1 second.
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  const lastRefreshed = dataUpdatedAt ? new Date(dataUpdatedAt) : null;
  const nextAt = dataUpdatedAt ? dataUpdatedAt + intervalMs : null;
  const remainingMs = nextAt ? Math.max(0, nextAt - now) : intervalMs;
  const secsLeft = Math.ceil(remainingMs / 1000);
  // 1 right after a fetch, smoothly decrements to 0 when next fetch is due
  const progress = Math.min(1, Math.max(0, remainingMs / intervalMs));

  return { secsLeft, progress, lastRefreshed };
}

/** Format a Date as HH:MM:SS, or "—" if null. */
export function fmtTime(d: Date | null): string {
  if (!d) return "—";
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}
