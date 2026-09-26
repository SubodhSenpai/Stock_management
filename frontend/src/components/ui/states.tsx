"use client";

import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import type { ApiError } from "@/lib/api";
import { Button } from "./Button";

/**
 * The three things a list can be other than "showing data": still loading, empty, or
 * broken. Every list renders all three, so a screen is never a blank rectangle and a
 * failure always offers a way out.
 */

/** A grey block standing in for a row while the first request is in flight. */
export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded bg-line/70", className)} aria-hidden />;
}

export function TableSkeleton({ rows = 6, columns = 5 }: { rows?: number; columns?: number }) {
  return (
    <div className="p-4 space-y-3" role="status" aria-label="Loading">
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <div key={rowIndex} className="flex gap-4">
          {Array.from({ length: columns }).map((__, columnIndex) => (
            <Skeleton
              key={columnIndex}
              className={cn("h-4 flex-1", columnIndex === 0 && "max-w-[8rem]")}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
  icon,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-16 text-center">
      {icon && <div className="text-brand-400">{icon}</div>}
      <h3 className="text-base font-semibold text-ink">{title}</h3>
      {description && <p className="max-w-sm text-sm text-ink-muted">{description}</p>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}

/**
 * A failed request, with the server's own message and the request id beneath it.
 *
 * The id is shown deliberately: it is in the server log against the same request, so a
 * bug report can be traced without guesswork.
 */
export function ErrorState({ error, onRetry }: { error: ApiError; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-16 text-center">
      <h3 className="text-base font-semibold text-rose-700">
        {error.isForbidden ? "You do not have access to this" : "Could not load this"}
      </h3>
      <p className="max-w-md text-sm text-ink-muted">{error.message}</p>
      {error.requestId && (
        <p className="font-mono text-xs text-ink-muted/80">Request {error.requestId}</p>
      )}
      {onRetry && !error.isForbidden && (
        <Button className="mt-3" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}
