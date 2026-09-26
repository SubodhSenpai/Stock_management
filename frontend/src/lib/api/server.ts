import "server-only";

import { cookies } from "next/headers";
import type { User } from "@/types/api";
import { API_BASE_URL } from "./client";

/**
 * Server-side reads, for data the first paint needs.
 *
 * The browser's cookies are not attached automatically to a fetch made on the server,
 * so they are forwarded explicitly. This is used for the signed-in user in the app
 * layout: fetching it here means the shell renders with the user's name and role
 * already in place, instead of flashing an empty bar while a client request runs.
 */

async function serverFetch<T>(path: string): Promise<T | null> {
  const cookieHeader = (await cookies()).toString();
  if (!cookieHeader) return null;

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      headers: { cookie: cookieHeader },
      // Session-scoped data must never be cached between requests or between users.
      cache: "no-store",
    });
    return response.ok ? ((await response.json()) as T) : null;
  } catch {
    // The API being down should render the signed-out state, not a 500 page.
    return null;
  }
}

/** The signed-in user, or null when there is no valid session. */
export function getCurrentUser(): Promise<User | null> {
  return serverFetch<User>("/auth/me");
}
