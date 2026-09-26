"use client";

import type { ReactNode } from "react";
import { Toaster } from "@/components/ui";
import { RealtimeProvider } from "@/providers/RealtimeProvider";
import { SessionProvider } from "@/providers/SessionProvider";
import { ToastProvider } from "@/providers/ToastProvider";
import type { User } from "@/types/api";
import { TopNav } from "./TopNav";

/**
 * Everything a signed-in page can rely on: the session, the live feed and toasts.
 *
 * The user is handed down from the server layout, so the bar renders with their name
 * and role already known rather than after a round trip.
 */
export function AppShell({ user, children }: { user: User; children: ReactNode }) {
  return (
    <SessionProvider user={user}>
      <ToastProvider>
        <RealtimeProvider>
          <div className="flex min-h-screen flex-col">
            <TopNav />
            <main className="flex-1">{children}</main>
          </div>
          <Toaster />
        </RealtimeProvider>
      </ToastProvider>
    </SessionProvider>
  );
}
