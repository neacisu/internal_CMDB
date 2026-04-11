/**
 * Auth API — login, logout, and current-user fetching.
 * Cookies are managed automatically by the browser (httpOnly, SameSite=lax).
 */

const BASE = "/api/v1";

export interface UserOut {
  user_id: string;
  email: string;
  username: string;
  role: string;
  is_active: boolean;
  last_login_at: string | null;
  force_password_change: boolean;
}

export interface LoginResult {
  force_password_change: boolean;
}

export class AuthError extends Error {
  constructor(
    public readonly status: number,
    message: string
  ) {
    super(message);
    this.name = "AuthError";
  }
}

/**
 * POST /auth/login — returns force_password_change flag on success.
 * Throws AuthError on 401/429, Error on network failures.
 */
export async function login(
  email: string,
  password: string
): Promise<LoginResult> {
  const res = await fetch(`${BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ email, password }),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new AuthError(res.status, text);
  }

  return res.json() as Promise<LoginResult>;
}

/**
 * POST /auth/logout — revokes the session cookie.
 * Always resolves (idempotent).
 */
export async function logout(): Promise<void> {
  try {
    await fetch(`${BASE}/auth/logout`, {
      method: "POST",
      credentials: "include",
    });
  } catch {
    // best-effort: ignore network errors on logout
  }
}

/**
 * GET /auth/me — returns the authenticated user's profile.
 * Returns null if unauthenticated (401).
 */
export async function getMe(): Promise<UserOut | null> {
  const res = await fetch(`${BASE}/auth/me`, {
    credentials: "include",
    cache: "no-store",
  });
  if (res.status === 401) return null;
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json() as Promise<UserOut>;
}

/**
 * POST /auth/password-reset — resets the current user's password.
 * Throws AuthError on failure.
 */
export async function resetPassword(
  currentPassword: string,
  newPassword: string
): Promise<void> {
  const res = await fetch(`${BASE}/auth/password-reset`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new AuthError(res.status, text);
  }
}
