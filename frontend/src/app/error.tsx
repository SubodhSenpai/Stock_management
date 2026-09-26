"use client";

import { useEffect } from "react";

/**
 * The last line of defence: an exception that escaped a page.
 *
 * `digest` is Next's server-side error id, printed here so a report can be matched to
 * the server log. The error itself is never shown, because it may describe internals.
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 px-4 text-center">
      <h1 className="text-lg font-semibold text-rose-700">Something went wrong</h1>
      <p className="max-w-md text-sm text-ink-muted">
        This page could not be displayed. Trying again is usually enough; if it is not,
        the details below identify what failed.
      </p>
      {error.digest && (
        <p className="font-mono text-xs text-ink-muted/80">Reference {error.digest}</p>
      )}
      <button
        type="button"
        onClick={reset}
        className="mt-2 rounded bg-accent-500 px-4 py-2 text-sm font-medium text-white hover:bg-accent-600"
      >
        Try again
      </button>
    </div>
  );
}
