/**
 * Tests for src/lib/auth.ts
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { login, logout, getMe, resetPassword } from "@/lib/auth";

// ---------------------------------------------------------------------------
// Mock fetch globally
// ---------------------------------------------------------------------------

function mockFetch(status: number, body: unknown) {
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
    statusText: String(status),
  } as Response);
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});
afterEach(() => {
  vi.unstubAllGlobals();
});

// ---------------------------------------------------------------------------
// login
// ---------------------------------------------------------------------------

describe("login", () => {
  it("returns force_password_change on success", async () => {
    vi.stubGlobal("fetch", mockFetch(200, { force_password_change: false }));
    const result = await login("a@b.com", "pass");
    expect(result.force_password_change).toBe(false);
  });

  it("throws AuthError(401) on bad credentials", async () => {
    vi.stubGlobal("fetch", mockFetch(401, { detail: "Invalid credentials." }));
    await expect(login("a@b.com", "wrong")).rejects.toMatchObject({
      name: "AuthError",
      status: 401,
    });
  });

  it("throws AuthError(429) on lockout", async () => {
    vi.stubGlobal("fetch", mockFetch(429, { detail: "Too many attempts" }));
    await expect(login("a@b.com", "x")).rejects.toMatchObject({ status: 429 });
  });
});

// ---------------------------------------------------------------------------
// logout
// ---------------------------------------------------------------------------

describe("logout", () => {
  it("resolves without error on success", async () => {
    vi.stubGlobal("fetch", mockFetch(204, null));
    await expect(logout()).resolves.toBeUndefined();
  });

  it("resolves even on network error (best-effort)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("network error"))
    );
    await expect(logout()).resolves.toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// getMe
// ---------------------------------------------------------------------------

describe("getMe", () => {
  it("returns user on 200", async () => {
    const user = {
      user_id: "u1",
      email: "a@b.com",
      username: "a",
      role: "admin",
      is_active: true,
      last_login_at: null,
      force_password_change: false,
    };
    vi.stubGlobal("fetch", mockFetch(200, user));
    await expect(getMe()).resolves.toMatchObject({ email: "a@b.com" });
  });

  it("returns null on 401", async () => {
    vi.stubGlobal("fetch", mockFetch(401, {}));
    await expect(getMe()).resolves.toBeNull();
  });
});

// ---------------------------------------------------------------------------
// resetPassword
// ---------------------------------------------------------------------------

describe("resetPassword", () => {
  it("resolves on 204", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 204,
        json: () => Promise.resolve(null),
        text: () => Promise.resolve(""),
      } as Response)
    );
    await expect(resetPassword("old", "new")).resolves.toBeUndefined();
  });

  it("throws AuthError(400) on wrong current password", async () => {
    vi.stubGlobal("fetch", mockFetch(400, { detail: "Current password is incorrect." }));
    await expect(resetPassword("wrong", "new1")).rejects.toMatchObject({
      status: 400,
    });
  });
});
