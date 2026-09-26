"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useRef, useState } from "react";
import { cn } from "@/lib/cn";
import type { NavItem } from "@/lib/config/navigation";
import { useOnClickOutside } from "@/lib/hooks/useOnClickOutside";

/**
 * One entry in the top bar: either a plain link or a dropdown.
 *
 * The menu closes on outside click, Escape and navigation, so it never stays open over
 * the page the user has just moved to.
 */
export function NavMenu({ item }: { item: NavItem }) {
  const [open, setOpen] = useState(false);
  const container = useRef<HTMLDivElement>(null);
  const pathname = usePathname();

  useOnClickOutside(container, () => setOpen(false), open);

  const isActive = item.href
    ? pathname.startsWith(item.href)
    : (item.children ?? []).some((child) => pathname.startsWith(child.href));

  const triggerClasses = cn(
    "rounded px-3 py-1.5 text-sm font-medium transition-colors whitespace-nowrap",
    isActive ? "bg-white/20 text-white" : "text-white/85 hover:bg-white/10 hover:text-white",
  );

  if (item.href) {
    return (
      <Link href={item.href} className={triggerClasses} aria-current={isActive ? "page" : undefined}>
        {item.label}
      </Link>
    );
  }

  return (
    <div ref={container} className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-haspopup="menu"
        className={cn(triggerClasses, "inline-flex items-center gap-1")}
      >
        {item.label}
        <span aria-hidden className="text-[10px] opacity-70">
          ▾
        </span>
      </button>

      {open && (
        <div
          role="menu"
          className="absolute left-0 z-40 mt-1 w-60 overflow-hidden rounded border border-line bg-sheet py-1 shadow-lg"
        >
          {item.children?.map((child) => (
            <Link
              key={child.href}
              href={child.href}
              role="menuitem"
              onClick={() => setOpen(false)}
              className={cn(
                "block px-3 py-2 text-sm transition-colors hover:bg-brand-50",
                pathname.startsWith(child.href) ? "text-brand-700 font-medium" : "text-ink",
              )}
            >
              {child.label}
              {child.description && (
                <span className="block text-xs text-ink-muted">{child.description}</span>
              )}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
