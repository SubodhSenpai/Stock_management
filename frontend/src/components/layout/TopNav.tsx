"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { cn } from "@/lib/cn";
import { navigationFor } from "@/lib/config/navigation";
import { useRealtimeStatus } from "@/providers/RealtimeProvider";
import { useSession } from "@/providers/SessionProvider";
import { NavMenu } from "./NavMenu";
import { UserMenu } from "./UserMenu";

/**
 * The application bar, in Odoo's plum.
 *
 * The menu is built from the navigation table filtered by role, so a staff user is
 * never shown a settings page they would be refused. On a phone the same table renders
 * as a single expandable list rather than a second, separate mobile menu.
 */
export function TopNav() {
  const { user } = useSession();
  const [mobileOpen, setMobileOpen] = useState(false);
  const pathname = usePathname();
  const items = navigationFor(user.role);

  // Navigating away should close the drawer, or it covers the new page.
  useEffect(() => setMobileOpen(false), [pathname]);

  return (
    <header className="no-print sticky top-0 z-30 bg-brand-600 shadow-sm">
      <div className="flex h-12 items-center gap-1 px-3">
        <Link
          href="/dashboard"
          className="mr-2 flex shrink-0 items-center gap-2 text-white"
          aria-label="StockSense home"
        >
          <span
            aria-hidden
            className="grid h-7 w-7 place-items-center rounded bg-white/20 text-sm font-bold"
          >
            S
          </span>
          <span className="hidden text-base font-semibold tracking-tight sm:block">StockSense</span>
        </Link>

        <nav aria-label="Main" className="hidden items-center gap-0.5 lg:flex">
          {items.map((item) => (
            <NavMenu key={item.label} item={item} />
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-2">
          <LiveIndicator />
          <UserMenu />
          <button
            type="button"
            onClick={() => setMobileOpen((value) => !value)}
            aria-expanded={mobileOpen}
            aria-label="Toggle navigation"
            className="rounded p-2 text-white hover:bg-white/10 lg:hidden"
          >
            <span aria-hidden>☰</span>
          </button>
        </div>
      </div>

      {mobileOpen && (
        <nav aria-label="Main" className="border-t border-white/20 px-3 pb-3 lg:hidden">
          {items.map((item) => (
            <div key={item.label} className="py-1">
              {item.href ? (
                <Link href={item.href} className="block py-1.5 text-sm font-medium text-white">
                  {item.label}
                </Link>
              ) : (
                <>
                  <p className="pt-2 text-xs uppercase tracking-wide text-white/60">{item.label}</p>
                  {item.children?.map((child) => (
                    <Link
                      key={child.href}
                      href={child.href}
                      className="block py-1.5 pl-3 text-sm text-white/90"
                    >
                      {child.label}
                    </Link>
                  ))}
                </>
              )}
            </div>
          ))}
        </nav>
      )}
    </header>
  );
}

/**
 * Whether the live feed is connected.
 *
 * Worth showing: when it is green the lists update by themselves, and when it is not
 * the user knows why a colleague's change has not appeared yet.
 */
function LiveIndicator() {
  const status = useRealtimeStatus();
  const label =
    status === "open" ? "Live" : status === "connecting" ? "Connecting" : "Offline";

  return (
    <span
      title={
        status === "open"
          ? "Connected: lists refresh as other people work"
          : "Not connected: refresh the page to see recent changes"
      }
      className="hidden items-center gap-1.5 rounded-full bg-white/15 px-2.5 py-1 text-xs text-white/90 sm:inline-flex"
    >
      <span
        aria-hidden
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          status === "open" && "bg-emerald-400",
          status === "connecting" && "animate-pulse bg-amber-300",
          status === "closed" && "bg-rose-400",
        )}
      />
      {label}
    </span>
  );
}
