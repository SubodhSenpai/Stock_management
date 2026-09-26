"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

/**
 * Transient feedback: "Validated WH/OUT/0003", "Not enough stock".
 *
 * Errors that belong to a field are rendered next to that field instead; this is for
 * outcomes that have nowhere else to appear.
 */

export type ToastVariant = "success" | "error" | "info" | "warning";

export interface Toast {
  id: number;
  variant: ToastVariant;
  message: string;
  /** Optional second line: the server's `details`, or a hint about what to do next. */
  hint?: string;
}

interface ToastContextValue {
  toasts: Toast[];
  notify: (variant: ToastVariant, message: string, hint?: string) => void;
  dismiss: (id: number) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const DISMISS_AFTER_MS = 5_000;
let nextId = 1;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const notify = useCallback(
    (variant: ToastVariant, message: string, hint?: string) => {
      const id = nextId++;
      setToasts((current) => [...current, { id, variant, message, hint }]);
      // Errors stay until dismissed: they usually carry something worth reading.
      if (variant !== "error") setTimeout(() => dismiss(id), DISMISS_AFTER_MS);
    },
    [dismiss],
  );

  const value = useMemo(() => ({ toasts, notify, dismiss }), [toasts, notify, dismiss]);
  return <ToastContext.Provider value={value}>{children}</ToastContext.Provider>;
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) throw new Error("useToast must be used inside a ToastProvider");
  return context;
}
