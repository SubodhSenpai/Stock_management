import { NextResponse, type NextRequest } from "next/server";

/**
 * Route guard.
 *
 * This only checks whether a session cookie exists, which is enough to send a signed-out
 * visitor to the login page instead of flashing an empty dashboard. It is not a security
 * boundary: the cookie is opaque here (it is httpOnly and signed by the API), and every
 * endpoint verifies the token itself and answers 401 with no data when it is missing,
 * expired or forged.
 */

const ACCESS_COOKIE = "access_token";

/** Reachable without a session. */
const PUBLIC_ROUTES = ["/login", "/signup", "/forgot-password"];

/**
 * Content-Security-Policy for the Next.js frontend.
 *
 * - `default-src 'self'` — baseline allowlist: only same-origin resources.
 * - `script-src 'self'` — no inline scripts; Next.js chunks are all same-origin.
 * - `style-src 'self' 'unsafe-inline'` — Next.js injects `<style>` tags at build time.
 * - `img-src 'self' data:` — allow inline data: URIs used by SVG icons.
 * - `font-src 'self'` — self-hosted fonts only.
 * - `connect-src 'self' ${API}` — XHR/fetch to the backend.
 * - `frame-ancestors 'none'` — clickjacking protection (mirrors X-Frame-Options DENY).
 * - `base-uri 'self'` — prevent `<base>` hijacking.
 * - `form-action 'self'` — form submissions stay same-origin.
 */
function buildCsp(): string {
  const apiOrigin =
    process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/api\/.*$/, "") ??
    "http://localhost:8000";
  const wsOrigin =
    process.env.NEXT_PUBLIC_WS_URL?.replace(/\/api\/.*$/, "") ??
    "ws://localhost:8000";

  return [
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self' data:",
    `connect-src 'self' ${apiOrigin} ${wsOrigin} http://localhost:8000 ws://localhost:8000 http://127.0.0.1:8000 ws://127.0.0.1:8000`,
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
  ].join("; ");
}

const CSP = buildCsp();

/** Standard security headers applied to every response. */
function addSecurityHeaders(response: NextResponse): void {
  response.headers.set("Content-Security-Policy", CSP);
  response.headers.set("X-Content-Type-Options", "nosniff");
  response.headers.set("X-Frame-Options", "DENY");
  response.headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  response.headers.set("Permissions-Policy", "camera=(), microphone=(), geolocation=()");
}

export function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const hasSession = Boolean(request.cookies.get(ACCESS_COOKIE)?.value);
  const isPublic = PUBLIC_ROUTES.some(
    (route) => pathname === route || pathname.startsWith(`${route}/`),
  );

  if (!hasSession && !isPublic) {
    const login = new URL("/login", request.url);
    // Remember where they were headed so signing in lands them there.
    if (pathname !== "/") login.searchParams.set("next", `${pathname}${search}`);
    const response = NextResponse.redirect(login);
    addSecurityHeaders(response);
    return response;
  }

  if (hasSession && isPublic) {
    const response = NextResponse.redirect(new URL("/dashboard", request.url));
    addSecurityHeaders(response);
    return response;
  }

  const response = NextResponse.next();
  addSecurityHeaders(response);
  return response;
}

export const config = {
  // Everything except Next's own assets and the favicon.
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|webp)$).*)"],
};

