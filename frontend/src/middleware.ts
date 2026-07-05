import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PUBLIC_PATHS = ["/login"];
const SESSION_COOKIE = "cmdb_session";

/**
 * Auth middleware — verify session via API, redirect unauthenticated users to
 * /login, and enforce the force_password_change gate.
 *
 * SEC-04: JWT verification is delegated to GET /api/v1/auth/verify on the
 * backend so the frontend never needs JWT_SECRET_KEY.
 */
export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const isPublic = PUBLIC_PATHS.some(
    (p) => pathname === p || pathname.startsWith(`${p}/`)
  );

  const token = request.cookies.get(SESSION_COOKIE)?.value;

  if (isPublic) {
    if (token && (await isValidToken(token, request))) {
      return NextResponse.redirect(new URL("/", request.url));
    }
    return NextResponse.next();
  }

  if (!token) {
    return redirectToLogin(request, pathname);
  }

  const payload = await verifyToken(token, request);
  if (!payload) {
    return redirectToLogin(request, pathname);
  }

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

async function isValidToken(token: string, request: NextRequest): Promise<boolean> {
  return (await verifyToken(token, request)) !== null;
}

interface JwtClaims {
  sub: string;
  role: string;
  force_password_change: boolean;
}

async function verifyToken(
  token: string,
  request: NextRequest
): Promise<JwtClaims | null> {
  const backendUrl =
    process.env.BACKEND_URL ||
    process.env.NEXT_PUBLIC_BACKEND_URL ||
    "http://127.0.0.1:4444";

  try {
    const verifyUrl = new URL("/api/v1/auth/verify", backendUrl);
    const resp = await fetch(verifyUrl.toString(), {
      headers: {
        Cookie: `${SESSION_COOKIE}=${token}`,
        "X-Forwarded-Host": request.headers.get("host") || "",
      },
      cache: "no-store",
    });
    if (!resp.ok) {
      return null;
    }
    return (await resp.json()) as JwtClaims;
  } catch {
    console.error(
      "[internalCMDB middleware] auth verify API unreachable — failing secure"
    );
    return null;
  }
}

function redirectToLogin(request: NextRequest, from: string): NextResponse {
  const loginUrl = new URL("/login", request.url);
  if (
    from &&
    from !== "/" &&
    from.startsWith("/") &&
    !from.startsWith("//") &&
    !from.includes("://")
  ) {
    loginUrl.searchParams.set("from", from);
  }
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico).*)",
  ],
};
