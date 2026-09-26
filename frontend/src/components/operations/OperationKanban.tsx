"use client";

import Link from "next/link";
import { Badge } from "@/components/ui";
import { cn } from "@/lib/cn";
import type { OperationConfig } from "@/lib/config/operations";
import { STATUS_STYLES } from "@/lib/config/status";
import { formatDate } from "@/lib/format";
import type { OperationStatus, OperationSummary } from "@/types/api";

/**
 * The kanban view: one column per status, as in Odoo.
 *
 * Grouping happens on the page that is already loaded rather than by refetching, so the
 * list and kanban views always agree about what they are showing.
 */
export function OperationKanban({
  operations,
  config,
}: {
  operations: OperationSummary[];
  config: OperationConfig;
}) {
  const columns = config.statuses.filter((status) => status !== "canceled");
  const grouped = new Map<OperationStatus, OperationSummary[]>(
    columns.map((status) => [status, []]),
  );
  for (const operation of operations) {
    grouped.get(operation.status)?.push(operation);
  }

  return (
    <div className="scrollbar-slim overflow-x-auto p-3">
      <div
        className="grid min-w-[52rem] gap-3"
        style={{ gridTemplateColumns: `repeat(${columns.length}, minmax(0, 1fr))` }}
      >
        {columns.map((status) => {
          const style = STATUS_STYLES[status];
          const cards = grouped.get(status) ?? [];

          return (
            <section key={status} className="rounded bg-canvas p-2" aria-label={style.label}>
              <header className="mb-2 flex items-center justify-between px-1">
                <h3 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-ink-muted">
                  <span aria-hidden className={cn("h-2 w-2 rounded-full", style.stepperClassName)} />
                  {style.label}
                </h3>
                <span className="text-xs text-ink-muted">{cards.length}</span>
              </header>

              <div className="flex flex-col gap-2">
                {cards.map((operation) => (
                  <Link
                    key={operation.id}
                    href={`/operations/${config.slug}/${operation.id}`}
                    className="sheet block p-2.5 transition-shadow hover:shadow-md"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <span className="font-mono text-xs font-semibold text-brand-700">
                        {operation.reference}
                      </span>
                      {operation.is_late && (
                        <Badge
                          className="bg-rose-100 text-rose-700 ring-rose-300"
                          title="Scheduled before today and still open"
                        >
                          Late
                        </Badge>
                      )}
                    </div>

                    {operation.partner && (
                      <p className="mt-1 truncate text-sm text-ink">{operation.partner.name}</p>
                    )}

                    <p className="mt-1 truncate text-xs text-ink-muted">
                      {operation.source_location.code} → {operation.dest_location.code}
                    </p>
                    <p className="mt-1 text-xs text-ink-muted">
                      {formatDate(operation.schedule_date)}
                    </p>
                  </Link>
                ))}

                {cards.length === 0 && (
                  <p className="px-1 py-6 text-center text-xs text-ink-muted">Nothing here</p>
                )}
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}
