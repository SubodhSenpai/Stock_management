"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { cn } from "@/lib/cn";
import { Button } from "./Button";

/**
 * A dialog.
 *
 * Built on `<dialog>` so the browser supplies the focus trap, the backdrop and Escape
 * handling rather than this file reimplementing them badly.
 */
export function Modal({
  open,
  title,
  description,
  onClose,
  footer,
  size = "md",
  children,
}: {
  open: boolean;
  title: string;
  description?: string;
  onClose: () => void;
  footer?: ReactNode;
  size?: "sm" | "md" | "lg";
  children: ReactNode;
}) {
  const dialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    if (open && !element.open) element.showModal();
    if (!open && element.open) element.close();
  }, [open]);

  if (!open) return null;

  return (
    <dialog
      ref={dialog}
      // Escape fires `cancel`; routing it through onClose keeps React's state in step.
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClose={onClose}
      className={cn(
        "m-auto w-[calc(100vw-2rem)] rounded-lg border border-line bg-sheet p-0 text-ink shadow-xl",
        "backdrop:bg-black/40",
        size === "sm" && "max-w-sm",
        size === "md" && "max-w-lg",
        size === "lg" && "max-w-3xl",
      )}
    >
      <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-3.5">
        <div>
          <h2 className="text-base font-semibold">{title}</h2>
          {description && <p className="mt-0.5 text-sm text-ink-muted">{description}</p>}
        </div>
        <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close">
          ✕
        </Button>
      </div>

      <div className="px-5 py-4">{children}</div>

      {footer && (
        <div className="flex justify-end gap-2 border-t border-line bg-canvas px-5 py-3">
          {footer}
        </div>
      )}
    </dialog>
  );
}

/**
 * "Are you sure?" for the one action that cannot be undone from the UI.
 *
 * Cancelling a document releases its reservation, so it is worth a second look.
 */
export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = "Confirm",
  destructive = false,
  pending = false,
  onConfirm,
  onClose,
}: {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  destructive?: boolean;
  pending?: boolean;
  onConfirm: () => void;
  onClose: () => void;
}) {
  return (
    <Modal
      open={open}
      title={title}
      onClose={onClose}
      size="sm"
      footer={
        <>
          <Button onClick={onClose} disabled={pending}>
            Keep it
          </Button>
          <Button
            variant={destructive ? "danger" : "primary"}
            onClick={onConfirm}
            loading={pending}
          >
            {confirmLabel}
          </Button>
        </>
      }
    >
      <p className="text-sm text-ink-muted">{message}</p>
    </Modal>
  );
}
