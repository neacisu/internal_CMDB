"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { FLEET_VITALS_SSE_URL, getFleetVitals, type FleetVital } from "./api";


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

// ---------------------------------------------------------------------------
// useFleetVitalsSSE — real-time fleet vitals via Server-Sent Events
// ---------------------------------------------------------------------------

const _SSE_FALLBACK_INTERVAL_MS = 6_000;   // poll interval when SSE unavailable
const _SSE_STALL_TIMEOUT_MS = 20_000;      // re-connect if no event for 20 s

/**
 * Maintains an up-to-date ``FleetVital[]`` by:
 * 1. Fetching an initial HTTP snapshot immediately (fast first paint)
 * 2. Opening an SSE connection to receive per-agent push updates
 * 3. Falling back to ``_SSE_FALLBACK_INTERVAL_MS`` polling if SSE fails
 *
 * Returns ``{ vitals, isLive }`` — ``isLive`` is true while the SSE
 * connection is healthy and false when falling back to polling.
 */
export function useFleetVitalsSSE(): { vitals: FleetVital[]; isLive: boolean } {
  const [vitals, setVitals] = useState<FleetVital[]>([]);
  const [isLive, setIsLive] = useState(false);

  // Stable merge helper: update one entry by host_code, or append
  const mergeVital = useCallback((incoming: FleetVital) => {
    setVitals((prev) => {
      const idx = prev.findIndex((v) => v.host_code === incoming.host_code);
      if (idx === -1) return [...prev, incoming];
      const next = [...prev];
      next[idx] = incoming;
      return next;
    });
  }, []);

  // ── Initial HTTP fetch so the page shows data before SSE connects ────────
  useEffect(() => {
    getFleetVitals().then(setVitals).catch(() => undefined);
  }, []);

  // ── SSE subscription with stall-detection and retry ─────────────────────
  const esRef = useRef<EventSource | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const stallRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearPoll = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  };
  const clearStall = () => {
    if (stallRef.current) { clearTimeout(stallRef.current); stallRef.current = null; }
  };

  const startFallbackPolling = useCallback(() => {
    setIsLive(false);
    clearPoll();
    pollRef.current = setInterval(() => {
      getFleetVitals().then(setVitals).catch(() => undefined);
    }, _SSE_FALLBACK_INTERVAL_MS);
  }, []);

  const resetStallTimer = useCallback((reconnect: () => void) => {
    clearStall();
    stallRef.current = setTimeout(reconnect, _SSE_STALL_TIMEOUT_MS);
  }, []);

  useEffect(() => {
    if (typeof EventSource === "undefined") {
      // Delay to avoid synchronous setState inside effect body (react-hooks/set-state-in-effect)
      const id = setTimeout(startFallbackPolling, 0);
      return () => clearTimeout(id);
    }

    let closed = false;

    function connect() {
      if (closed) return;

      const es = new EventSource(FLEET_VITALS_SSE_URL, { withCredentials: true });
      esRef.current = es;

      function reconnectAfterDelay() {
        if (!closed) { es.close(); connect(); }
      }

      const scheduleReconnect = () => {
        clearStall();
        if (!closed) {
          startFallbackPolling();
          setTimeout(reconnectAfterDelay, Math.min(10_000, _SSE_FALLBACK_INTERVAL_MS));
        }
      };

      resetStallTimer(scheduleReconnect);

      es.addEventListener("snapshot", (e: MessageEvent) => {
        try {
          const arr: FleetVital[] = JSON.parse(e.data) as FleetVital[];
          setVitals(arr);
          setIsLive(true);
          clearPoll();
          resetStallTimer(scheduleReconnect);
        } catch { /* ignore malformed */ }
      });

      es.addEventListener("vital", (e: MessageEvent) => {
        try {
          const v: FleetVital = JSON.parse(e.data) as FleetVital;
          mergeVital(v);
          setIsLive(true);
          clearPoll();
          resetStallTimer(scheduleReconnect);
        } catch { /* ignore malformed */ }
      });

      es.addEventListener("ping", () => {
        resetStallTimer(scheduleReconnect);
      });

      es.onerror = () => {
        es.close();
        scheduleReconnect();
      };
    }

    connect();

    return () => {
      closed = true;
      clearStall();
      clearPoll();
      esRef.current?.close();
    };
  }, [mergeVital, resetStallTimer, startFallbackPolling]);

  return { vitals, isLive };
}
