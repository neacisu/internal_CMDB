/**
 * middleware.test.ts
 *
 * Unit tests for Next.js auth middleware (SEC-04 API verification).
 */
import { describe, it, expect, vi, beforeEach } from "vitest";

import { middleware } from "@/middleware";
import type { NextRequest } from "next/server";

function makeRequest(
  pathname: string,
  cookieValue?: string,
  baseUrl = "http://localhost:3000"
) {
  const url = new URL(pathname, baseUrl);
  const headers = new Headers();
  const cookies = cookieValue
    ? new Map([["cmdb_session", { name: "cmdb_session", value: cookieValue }]])
    : new Map();

  const request = {
    nextUrl: url,
    url: url.toString(),
    cookies: {
      get: (name: string) => cookies.get(name),
    },
    headers,
  };

  return request as unknown as NextRequest;
}

function validClaims(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    sub: "user-123",
    role: "admin",
    force_password_change: false,
    ...overrides,
  };
}

beforeEach(() => {
  vi.restoreAllMocks();
  process.env.BACKEND_URL = "http://127.0.0.1:4444";
});

describe("middleware — unauthenticated user", () => {
  it("redirects to /login when no cookie on protected route", async () => {
    vi.stubGlobal("fetch", vi.fn());
    const req = makeRequest("/hosts");
    const res = await middleware(req);
    expect(res.status).toBe(307);
    expect(res.headers.get("location")).toMatch(/\/login/);
  });
});

describe("middleware — API verify integration", () => {
  it("returns next() when verify API returns valid claims", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => validClaims(),
      })
    );
    const req = makeRequest("/hosts", "valid_token");
    const res = await middleware(req);
    expect(res.status).not.toBe(307);
  });

  it("redirects to /login when verify API returns non-OK", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, json: async () => ({}) })
    );
    const req = makeRequest("/hosts", "bad_token");
    const res = await middleware(req);
    expect(res.status).toBe(307);
  });

  it("redirects to /login when verify API is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network down")));
    const req = makeRequest("/hosts", "some_token");
    const res = await middleware(req);
    expect(res.status).toBe(307);
  });
});

describe("middleware — force_password_change gate", () => {
  it("redirects to /settings when force_password_change=true", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => validClaims({ force_password_change: true }),
      })
    );
    const req = makeRequest("/hosts", "force_token");
    const res = await middleware(req);
    expect(res.status).toBe(307);
    const location = res.headers.get("location") ?? "";
    expect(location).toContain("/settings");
    expect(location).toContain("tab=password");
  });
});

describe("middleware — public paths", () => {
  it("returns next() on /login without cookie", async () => {
    vi.stubGlobal("fetch", vi.fn());
    const req = makeRequest("/login");
    const res = await middleware(req);
    expect(res.status).not.toBe(307);
  });
});

describe("middleware — static bypass config", () => {
  it("exports matcher config that excludes _next/static paths", async () => {
    const { config } = await import("@/middleware");
    expect(config.matcher[0]).toContain("_next/static");
  });
});
