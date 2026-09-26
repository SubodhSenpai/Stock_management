"use client";

import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

/**
 * Odoo's control panel: the bar above every list.
 *
 * Title and the New button on the left, search and view switcher on the right, filters
 * on the row beneath. Every list screen uses it, which is what makes them feel like one
 * application rather than a set of pages.
 */
export function ControlPanel({
  title,
  subtitle,
  actions,
  search,
  filters,
  viewToggle,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  search?: ReactNode;
  filters?: ReactNode;
  viewToggle?: ReactNode;
}) {
  return (
    <div className="no-print border-b border-line bg-sheet">
      <div className="flex flex-wrap items-center gap-3 px-4 py-3">
        <div className="flex min-w-0 items-center gap-3">
          <div className="min-w-0">
            <h1 className="truncate text-lg font-semibold text-brand-700">{title}</h1>
            {subtitle && <p className="truncate text-xs text-ink-muted">{subtitle}</p>}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </div>

        <div className="ml-auto flex flex-1 items-center justify-end gap-2 sm:flex-none">
          {search && <div className="w-full sm:w-72">{search}</div>}
          {viewToggle}
        </div>
      </div>

      {filters && (
        <div className="flex flex-wrap items-center gap-2 border-t border-line/70 px-4 py-2">
          {filters}
        </div>
      )}
    </div>
  );
}

/** A filter chip: on and off, with the count when it has one. */
export function FilterChip({
  active,
  count,
  onClick,
  children,
}: {
  active: boolean;
  count?: number;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors",
        active
          ? "border-brand-500 bg-brand-500 text-white"
          : "border-line bg-white text-ink-muted hover:border-brand-400 hover:text-brand-700",
      )}
    >
      {children}
      {count !== undefined && (
        <span className={cn("rounded-full px-1.5", active ? "bg-white/25" : "bg-canvas")}>
          {count}
        </span>
      )}
    </button>
  );
}

/** List / Kanban, as in the top-right corner of an Odoo list. */
export function ViewToggle({
  view,
  onChange,
}: {
  view: "list" | "kanban";
  onChange: (view: "list" | "kanban") => void;
}) {
  const options = [
    { key: "list" as const, label: "List", icon: "☰" },
    { key: "kanban" as const, label: "Kanban", icon: "▦" },
  ];

  return (
    <div className="flex shrink-0 overflow-hidden rounded border border-line" role="group" aria-label="View">
      {options.map((option) => (
        <button
          key={option.key}
          type="button"
          onClick={() => onChange(option.key)}
          aria-pressed={view === option.key}
          title={`${option.label} view`}
          className={cn(
            "px-2.5 py-1.5 text-sm transition-colors",
            view === option.key
              ? "bg-brand-600 text-white"
              : "bg-white text-ink-muted hover:bg-brand-50",
          )}
        >
          <span aria-hidden>{option.icon}</span>
          <span className="sr-only">{option.label} view</span>
        </button>
      ))}
    </div>
  );
}
