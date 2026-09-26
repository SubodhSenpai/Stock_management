"use client";

import { cn } from "@/lib/cn";
import { useToast, type ToastVariant } from "@/providers/ToastProvider";

const VARIANT_STYLES: Record<ToastVariant, string> = {
  success: "border-emerald-300 bg-emerald-50 text-emerald-900",
  error: "border-rose-300 bg-rose-50 text-rose-900",
  warning: "border-amber-300 bg-amber-50 text-amber-900",
  info: "border-sky-300 bg-sky-50 text-sky-900",
};

/**
 * Where toasts appear.
 *
 * `aria-live="polite"` so a screen reader announces the outcome of an action without
 * interrupting whatever the user is doing.
 */
export function Toaster() {
  const { toasts, dismiss } = useToast();
  if (toasts.length === 0) return null;

  return (
    <div
      aria-live="polite"
      className="no-print pointer-events-none fixed bottom-4 right-4 z-50 flex w-full max-w-sm flex-col gap-2"
    >
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={cn(
            "pointer-events-auto flex items-start gap-3 rounded border px-4 py-3 shadow-lg",
            VARIANT_STYLES[toast.variant],
          )}
        >
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium break-words">{toast.message}</p>
            {toast.hint && <p className="mt-0.5 text-xs opacity-80 break-words">{toast.hint}</p>}
          </div>
          <button
            type="button"
            onClick={() => dismiss(toast.id)}
            aria-label="Dismiss"
            className="shrink-0 text-sm opacity-60 hover:opacity-100"
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  );
}
