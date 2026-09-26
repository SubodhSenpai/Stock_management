"use client";

import { useId, type ReactNode } from "react";
import { cn } from "@/lib/cn";

/**
 * Label, control and message, wired together.
 *
 * The control is rendered through a callback so it receives the generated id and the
 * aria attributes. That way every input in the app is labelled and every error is
 * announced, without each form remembering to do it.
 */
export function Field({
  label,
  error,
  hint,
  required,
  className,
  children,
}: {
  label: string;
  error?: string;
  /** Shown while there is no error: the rule, e.g. "6-12 characters". */
  hint?: string;
  required?: boolean;
  className?: string;
  children: (props: {
    id: string;
    "aria-invalid": boolean | undefined;
    "aria-describedby": string | undefined;
  }) => ReactNode;
}) {
  const id = useId();
  const messageId = `${id}-message`;
  const message = error ?? hint;

  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <label
        htmlFor={id}
        className="text-xs font-medium text-ink-muted uppercase tracking-wide"
      >
        {label}
        {required && (
          <span className="text-rose-600 ml-0.5" aria-hidden>
            *
          </span>
        )}
      </label>

      {children({
        id,
        "aria-invalid": error ? true : undefined,
        "aria-describedby": message ? messageId : undefined,
      })}

      {message && (
        <p
          id={messageId}
          role={error ? "alert" : undefined}
          className={cn("text-xs", error ? "text-rose-600" : "text-ink-muted")}
        >
          {message}
        </p>
      )}
    </div>
  );
}
