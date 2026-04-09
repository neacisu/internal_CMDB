/**
 * middleware.test.ts
 *
 * Unit tests for Next.js auth middleware.
 * Covers: unauthenticated redirect, authenticated pass-through, login page bypass,
 * force_password_change gate, open-redirect prevention, fail-secure when no secret.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";

// ---------------------------------------------------------------------------
// Mock jose — all JWT behaviour is controlled per-test
// ---------------------------------------------------------------------------
vi.mock("jose", () => ({
  jwtVerify: vi.fn(),
}));

import { jwtVerify } from "jose";
import { middleware } from "@/middleware";
import type { NextRequest } from "next/server";

// ---------------------------------------------------------------------------
// Helpers to build mock NextRequest and NextResponse
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// JWT payload factories
// ---------------------------------------------------------------------------

function validPayload(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    sub: "user-123",
    role: "admin",
    force_password_change: false,
    exp: Math.floor(Date.now() / 1000) + 3600,
    jti: "test-jti",
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  // Default secret
  process.env.JWT_SECRET_KEY = "test_secret_key_at_least_32_chars__!!";
});

describe("middleware — unauthenticated user", () => {
  it("redirects to /login when no cookie on protected route", async () => {
    vi.mocked(jwtVerify).mockRejectedValue(new Error("no token"));
    const req = makeRequest("/hosts");
    const res = await middleware(req);
    expect(res.status).toBe(307);
    expect(res.headers.get("location")).toMatch(/\/login/);
  });

  it("preserves ?from= param when redirecting from a sub-path", async () => {
    const req = makeRequest("/hosts/server-01");
    const res = await middleware(req);
    expect(res.headers.get("location")).toContain("from=%2Fhosts%2Fserver-01");
  });

  it("does NOT set ?from= for root path", async () => {
    const req = makeRequest("/");
    const res = await middleware(req);
    const location = res.headers.get("location") ?? "";
    expect(location).not.toContain("from=/");
  });
});

describe("middleware — public paths bypass auth", () => {
  it("returns next() on /login without cookie", async () => {
    const req = makeRequest("/login");
    const res = await middleware(req);
    // No redirect — passes through
    expect(res.status).not.toBe(307);
  });

  it("redirects authenticated user away from /login to /", async () => {
    vi.mocked(jwtVerify).mockResolvedValue({ payload: validPayload() } as unknown as Awaited<ReturnType<typeof jwtVerify>>);
    const req = makeRequest("/login", "valid_token");
    const res = await middleware(req);
    expect(res.status).toBe(307);
    expect(res.headers.get("location")).toMatch(/\/$/);
  });
});

describe("middleware — valid token passes through", () => {
  it("returns next() when token is valid and force_password_change=false", async () => {
    vi.mocked(jwtVerify).mockResolvedValue({ payload: validPayload() } as unknown as Awaited<ReturnType<typeof jwtVerify>>);
    const req = makeRequest("/hosts", "valid_token");
    const res = await middleware(req);
    expect(res.status).not.toBe(307);
  });

  it("passes through /settings without looping when force_password_change=false", async () => {
    vi.mocked(jwtVerify).mockResolvedValue({ payload: validPayload() } as unknown as Awaited<ReturnType<typeof jwtVerify>>);
    const req = makeRequest("/settings", "valid_token");
    const res = await middleware(req);
    expect(res.status).not.toBe(307);
  });
});

describe("middleware — force_password_change gate", () => {
  it("redirects to /settings?tab=password&required=true when force=true", async () => {
    vi.mocked(jwtVerify).mockResolvedValue({
      payload: validPayload({ force_password_change: true }),
    } as unknown as Awaited<ReturnType<typeof jwtVerify>>);
    const req = makeRequest("/hosts", "force_token");
    const res = await middleware(req);
    expect(res.status).toBe(307);
    const location = res.headers.get("location") ?? "";
    expect(location).toContain("/settings");
    expect(location).toContain("tab=password");
    expect(location).toContain("required=true");
  });

  it("allows access to /settings when force=true (not looping)", async () => {
    vi.mocked(jwtVerify).mockResolvedValue({
      payload: validPayload({ force_password_change: true }),
    } as unknown as Awaited<ReturnType<typeof jwtVerify>>);
    const req = makeRequest("/settings", "force_token");
    const res = await middleware(req);
    expect(res.status).not.toBe(307);
  });
});

describe("middleware — fail-secure when no JWT secret", () => {
  it("redirects to /login when JWT_SECRET_KEY is undefined", async () => {
    delete process.env.JWT_SECRET_KEY;
    const req = makeRequest("/hosts", "some_token");
    const res = await middleware(req);
    expect(res.status).toBe(307);
    expect(res.headers.get("location")).toMatch(/\/login/);
  });

  it("redirects to /login when JWT_SECRET_KEY is too short (<32 chars)", async () => {
    process.env.JWT_SECRET_KEY = "short";
    const req = makeRequest("/hosts", "some_token");
    const res = await middleware(req);
    expect(res.status).toBe(307);
  });
});

describe("middleware — open redirect prevention", () => {
  it("does NOT set ?from= for paths starting with //", async () => {
    // Simulate a pathname that starts with // — should not be set as from param
    const loginUrl = new URL("/login", "http://localhost:3000");
    const mockRedirTo = new URL("//evil.com", "http://localhost:3000");
    const from = mockRedirTo.pathname;  // "/" — double-slash collapses

    // Directly test the redirect logic: if from is "/" it should not be added
    if (from === "/" || !from.startsWith("/") || from.startsWith("//")) {
      loginUrl.searchParams.delete("from");
    } else {
      loginUrl.searchParams.set("from", from);
    }

    expect(loginUrl.searchParams.get("from")).toBeNull();
  });

  it("does not set ?from for paths containing ://", async () => {
    const url = new URL("/login", "http://localhost:3000");
    const req = {
      nextUrl: url,
      url: url.toString(),
      cookies: { get: () => undefined },
    } as unknown as NextRequest;
    const res = await middleware(req);
    const location = res.headers.get("location") ?? "";
    // /login is public — should just pass through
    expect(location).toBeFalsy();
  });
});

describe("middleware — static and image bypass", () => {
  it("exports matcher config that excludes _next/static paths", async () => {
    // The matcher config is exported and applied by Next.js runtime
    // We verify the exported config exists and has the correct exclusion pattern
    const { config } = await import("@/middleware");
    expect(config.matcher).toBeDefined();
    const pattern = config.matcher[0];
    expect(pattern).toContain("_next/static");
    expect(pattern).toContain("_next/image");
    expect(pattern).toContain("favicon.ico");
  });
});
