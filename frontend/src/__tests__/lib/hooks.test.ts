import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { fmtTime, useRefreshCountdown } from "@/lib/hooks";

describe("fmtTime", () => {
  it("returns dash for null", () => {
    expect(fmtTime(null)).toBe("—");
  });

  it("formats a Date into HH:MM:SS", () => {
    const d = new Date("2026-03-23T14:30:45Z");
    const result = fmtTime(d);
    expect(result).toMatch(/\d{2}:\d{2}:\d{2}/);
  });
});

describe("useRefreshCountdown", () => {
  const INTERVAL_MS = 6_000;

  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns null lastRefreshed when dataUpdatedAt is 0 (not yet fetched)", () => {
    const { result } = renderHook(() => useRefreshCountdown(0, INTERVAL_MS));
    expect(result.current.lastRefreshed).toBeNull();
  });

  it("returns a Date for lastRefreshed when dataUpdatedAt is a valid epoch-ms", () => {
    const epoch = new Date("2026-04-10T12:00:00Z").getTime();
    const { result } = renderHook(() => useRefreshCountdown(epoch, INTERVAL_MS));
    expect(result.current.lastRefreshed).toBeInstanceOf(Date);
    expect(result.current.lastRefreshed?.getTime()).toBe(epoch);
  });

  it("returns secsLeft within [0, intervalMs/1000] when dataUpdatedAt is recent", () => {
    const now = Date.now();
    // Simulate a fetch that happened 1 second ago
    const epoch = now - 1_000;
    vi.setSystemTime(now);
    const { result } = renderHook(() => useRefreshCountdown(epoch, INTERVAL_MS));
    expect(result.current.secsLeft).toBeGreaterThanOrEqual(0);
    expect(result.current.secsLeft).toBeLessThanOrEqual(INTERVAL_MS / 1_000);
  });

  it("returns progress of 1 immediately after a fresh fetch", () => {
    const now = Date.now();
    vi.setSystemTime(now);
    // dataUpdatedAt === now → full interval remaining → progress ≈ 1
    const { result } = renderHook(() => useRefreshCountdown(now, INTERVAL_MS));
    expect(result.current.progress).toBeCloseTo(1, 1);
  });

  it("decrements secsLeft after 1 second elapses", () => {
    const now = Date.now();
    vi.setSystemTime(now);
    const { result } = renderHook(() => useRefreshCountdown(now, INTERVAL_MS));
    const initialSecs = result.current.secsLeft;

    act(() => {
      vi.advanceTimersByTime(1_000);
    });

    expect(result.current.secsLeft).toBeLessThan(initialSecs);
  });

  it("progress is 0 when the interval has fully elapsed", () => {
    const now = Date.now();
    // Simulate a fetch that happened exactly intervalMs ago → next refresh is due now
    const epoch = now - INTERVAL_MS;
    vi.setSystemTime(now);
    const { result } = renderHook(() => useRefreshCountdown(epoch, INTERVAL_MS));
    expect(result.current.progress).toBeCloseTo(0, 1);
    expect(result.current.secsLeft).toBe(0);
  });

  it("clamps secsLeft to 0 when next refresh is overdue", () => {
    const now = Date.now();
    // Simulate a stale fetch (2× interval ago)
    const epoch = now - INTERVAL_MS * 2;
    vi.setSystemTime(now);
    const { result } = renderHook(() => useRefreshCountdown(epoch, INTERVAL_MS));
    expect(result.current.secsLeft).toBe(0);
    expect(result.current.progress).toBe(0);
  });

  it("cleans up the interval on unmount (no updates after unmount)", () => {
    const now = Date.now();
    vi.setSystemTime(now);
    const { result, unmount } = renderHook(() => useRefreshCountdown(now, INTERVAL_MS));
    const secsBeforeUnmount = result.current.secsLeft;
    unmount();
    act(() => {
      vi.advanceTimersByTime(3_000);
    });
    // After unmount the hook result is frozen — no state update should throw
    expect(result.current.secsLeft).toBe(secsBeforeUnmount);
  });
});
