import { describe, it, expect } from "vitest";
import { fmtTime } from "@/lib/hooks";

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
