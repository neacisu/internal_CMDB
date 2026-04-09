import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useWebSocket } from "@/lib/useWebSocket";

describe("useWebSocket", () => {
  class MockWebSocket {
    static readonly CONNECTING = 0;
    static readonly OPEN = 1;
    static readonly CLOSING = 2;
    static readonly CLOSED = 3;
    readyState = MockWebSocket.CONNECTING;
    onopen: (() => void) | null = null;
    onclose: (() => void) | null = null;
    onmessage: ((ev: { data: string }) => void) | null = null;
    send = vi.fn();
    close = vi.fn(() => {
      this.readyState = MockWebSocket.CLOSED;
      this.onclose?.();
    });
    constructor(public url: string) {
      queueMicrotask(() => {
        this.readyState = MockWebSocket.OPEN;
        this.onopen?.();
      });
    }
  }

  beforeEach(() => {
    vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
    Object.defineProperty(globalThis.window, "location", {
      value: { protocol: "http:", host: "localhost:3333" },
      writable: true,
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("connects and exposes connected state", async () => {
    const { result } = renderHook(() =>
      useWebSocket<{ x: number }>({
        url: "/ws/live",
        enabled: true,
      }),
    );
    await act(async () => {
      await Promise.resolve();
    });
    expect(result.current.state).toBe("connected");
  });
});
