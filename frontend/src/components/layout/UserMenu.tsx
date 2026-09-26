"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { initials, userLabel } from "@/lib/format";
import { useOnClickOutside } from "@/lib/hooks/useOnClickOutside";
import { useSession } from "@/providers/SessionProvider";

/** The avatar menu: who is signed in, their profile, and the way out. */
export function UserMenu() {
  const { user, signOut } = useSession();
  const [open, setOpen] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const container = useRef<HTMLDivElement>(null);

  useOnClickOutside(container, () => setOpen(false), open);

  const name = userLabel(user);

  return (
    <div ref={container} className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label={`Account menu for ${name}`}
        className="flex items-center gap-2 rounded-full py-1 pl-1 pr-2 text-white/90 transition-colors hover:bg-white/10"
      >
        <span
          aria-hidden
          className="grid h-7 w-7 place-items-center rounded-full bg-white/20 text-xs font-semibold"
        >
          {initials(name)}
        </span>
        <span className="hidden text-sm sm:block">{name}</span>
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 z-40 mt-1 w-56 overflow-hidden rounded border border-line bg-sheet py-1 shadow-lg"
        >
          <div className="border-b border-line px-3 py-2">
            <p className="truncate text-sm font-medium text-ink">{name}</p>
            <p className="truncate text-xs text-ink-muted">{user.email}</p>
            <p className="mt-1 text-xs capitalize text-brand-600">{user.role}</p>
          </div>

          <Link
            href="/profile"
            role="menuitem"
            onClick={() => setOpen(false)}
            className="block px-3 py-2 text-sm hover:bg-brand-50"
          >
            My Profile
          </Link>

          <button
            type="button"
            role="menuitem"
            disabled={signingOut}
            onClick={() => {
              setSigningOut(true);
              void signOut();
            }}
            className="block w-full px-3 py-2 text-left text-sm text-rose-700 hover:bg-rose-50 disabled:opacity-60"
          >
            {signingOut ? "Signing out..." : "Log out"}
          </button>
        </div>
      )}
    </div>
  );
}
