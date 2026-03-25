import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { cn, formatBytes, formatDate, timeAgo } from "@/lib/utils";

describe("cn", () => {
  it("merges tailwind classes", () => {
    expect(cn("px-2", "px-4")).toBe("px-4");
  });

  it("handles conditional classes", () => {
    const showHidden = false;
    expect(cn("text-sm", showHidden && "hidden", "font-bold")).toBe("text-sm font-bold");
  });
});

describe("formatBytes", () => {
  it("returns dash for null/undefined/zero", () => {
    expect(formatBytes(null)).toBe("—");
    expect(formatBytes(undefined)).toBe("—");
    expect(formatBytes(0)).toBe("—");
  });

  it("formats bytes to human-readable sizes", () => {
    expect(formatBytes(1024)).toBe("1 KB");
    expect(formatBytes(1024 * 1024)).toBe("1 MB");
    expect(formatBytes(1024 * 1024 * 1024)).toBe("1 GB");
  });

  it("respects decimal precision", () => {
    expect(formatBytes(1536, 2)).toBe("1.5 KB");
  });
});

describe("formatDate", () => {
  it("returns dash for null/undefined", () => {
    expect(formatDate(null)).toBe("—");
    expect(formatDate(undefined)).toBe("—");
  });

  it("formats ISO string to locale date", () => {
    const result = formatDate("2026-03-23T12:00:00Z");
    expect(result).toContain("2026");
    expect(result).toContain("Mar");
  });
});

describe("timeAgo", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-03-23T12:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns dash for null/undefined", () => {
    expect(timeAgo(null)).toBe("—");
    expect(timeAgo(undefined)).toBe("—");
  });

  it("returns 'just now' for recent timestamps", () => {
    expect(timeAgo("2026-03-23T12:00:00Z")).toBe("just now");
  });

  it("returns minutes ago", () => {
    expect(timeAgo("2026-03-23T11:55:00Z")).toBe("5m ago");
  });

  it("returns hours ago", () => {
    expect(timeAgo("2026-03-23T09:00:00Z")).toBe("3h ago");
  });

  it("returns days ago", () => {
    expect(timeAgo("2026-03-21T12:00:00Z")).toBe("2d ago");
  });
});
