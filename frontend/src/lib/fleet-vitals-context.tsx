"use client";

import { createContext, useContext, type ReactNode } from "react";
import { useFleetVitalsSSE } from "@/lib/hooks";
import type { FleetVital } from "@/lib/api";

interface FleetVitalsContextValue {
  vitals: FleetVital[];
  isLive: boolean;
}

const FleetVitalsContext = createContext<FleetVitalsContextValue | null>(null);

/** Single SSE subscription shared across dashboard components. */
export function FleetVitalsProvider({ children }: Readonly<{ children: ReactNode }>) {
  const value = useFleetVitalsSSE();
  return (
    <FleetVitalsContext.Provider value={value}>{children}</FleetVitalsContext.Provider>
  );
}

export function useFleetVitalsContext(): FleetVitalsContextValue {
  const ctx = useContext(FleetVitalsContext);
  if (!ctx) {
    throw new Error("useFleetVitalsContext must be used within FleetVitalsProvider");
  }
  return ctx;
}
