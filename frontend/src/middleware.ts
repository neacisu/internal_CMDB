import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { jwtVerify } from "jose";

const PUBLIC_PATHS = ["/login"];
const SESSION_COOKIE = "cmdb_session";

/**
 * Auth middleware — verify JWT, redirect unauthenticated users to /login,
 * and enforce the force_password_change gate.
 *
 * Uses jose (Edge Runtime compatible — no Node.js crypto).
 * JWT_SECRET_KEY is injected at runtime via Docker env, NOT build arg.
 * If JWT_SECRET_KEY is undefined at runtime: fail-secure (redirect to /login).
 */
export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const isPublic = PUBLIC_PATHS.some(
    (p) => pathname === p || pathname.startsWith(`${p}/`)
  );

  const token = request.cookies.get(SESSION_COOKIE)?.value;

  if (isPublic) {
    // If already authenticated, redirect away from /login
    if (token && (await isValidToken(token))) {
      return NextResponse.redirect(new URL("/", request.url));
    }
    return NextResponse.next();
  }

  // Protected route — must have valid token
  if (!token) {
    return redirectToLogin(request, pathname);
  }

  const payload = await verifyToken(token);
  if (!payload) {
    return redirectToLogin(request, pathname);
  }

  // force_password_change gate: must change password before doing anything else
  if (
    payload.force_password_change === true &&
    pathname !== "/settings" &&
    !pathname.startsWith("/settings/")
  ) {
    const settingsUrl = new URL("/settings", request.url);
    settingsUrl.searchParams.set("tab", "password");
    settingsUrl.searchParams.set("required", "true");
    return NextResponse.redirect(settingsUrl);
  }

  return NextResponse.next();
}

async function isValidToken(token: string): Promise<boolean> {
  return (await verifyToken(token)) !== null;
}

interface JwtClaims {
  sub: string;
  role: string;
  force_password_change: boolean;
  exp: number;
  jti: string;
}

async function verifyToken(token: string): Promise<JwtClaims | null> {
  const secret = process.env.JWT_SECRET_KEY;
  if (!secret || secret.length < 32) {
    console.error(
      "[internalCMDB middleware] JWT_SECRET_KEY not configured — failing secure"
    );
    return null;
  }

  try {
    const { payload } = await jwtVerify(
      token,
      new TextEncoder().encode(secret),
      { algorithms: ["HS256"], clockTolerance: 30 }
    );
    return payload as unknown as JwtClaims;
  } catch {
    return null;
  }
}

function redirectToLogin(request: NextRequest, from: string): NextResponse {
  const loginUrl = new URL("/login", request.url);
  // Only preserve same-origin relative paths — prevent open redirect
  if (from && from !== "/" && from.startsWith("/") && !from.startsWith("//") && !from.includes("://")) {
    loginUrl.searchParams.set("from", from);
  }
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: [
    /*
     * Match all paths except:
     * - _next/static (static files)
     * - _next/image  (image optimisation)
     * - favicon.ico
     * NOTE: /api/v1/* requests are proxied through Next.js rewrites to FastAPI.
     * FastAPI handles auth independently for API paths.
     */
    "/((?!_next/static|_next/image|favicon.ico).*)",
  ],
};

