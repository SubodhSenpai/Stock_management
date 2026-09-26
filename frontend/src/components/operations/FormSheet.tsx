import type { ReactNode } from "react";
import { FormAlert } from "@/components/auth/FormAlert";

/**
 * The Odoo form view: a white sheet with the title and status at the top, the action
 * buttons above it, and the fields laid out in two columns beneath.
 *
 * Shared by the document form and the document detail page so the two look identical —
 * the only difference between editing and viewing is whether the controls are enabled.
 */
export function FormSheet({
  title,
  subtitle,
  status,
  actions,
  formError,
  children,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  /** The status stepper, shown at the top right as in Odoo. */
  status?: ReactNode;
  actions?: ReactNode;
  formError?: string;
  children: ReactNode;
}) {
  return (
    <div className="mx-auto max-w-5xl px-4 py-5">
      {actions && (
        <div className="no-print mb-3 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">{actions}</div>
        </div>
      )}

      <div className="sheet p-5 sm:p-7">
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line pb-4">
          <div className="min-w-0">
            <h1 className="truncate text-xl font-semibold text-brand-700">{title}</h1>
            {subtitle && <p className="mt-0.5 text-sm text-ink-muted">{subtitle}</p>}
          </div>
          {status}
        </div>

        {formError && (
          <div className="mt-4">
            <FormAlert message={formError} />
          </div>
        )}

        {children}
      </div>
    </div>
  );
}

/** A group of fields, two per row on anything wider than a phone. */
export function FormSection({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <section className="mt-5">
      {title && (
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-brand-700">
          {title}
        </h2>
      )}
      <div className="grid gap-x-8 gap-y-4 sm:grid-cols-2">{children}</div>
    </section>
  );
}

/** A read-only label and value, for the detail view. */
export function ReadField({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs font-medium uppercase tracking-wide text-ink-muted">{label}</span>
      <span className="text-sm text-ink">{children}</span>
    </div>
  );
}
