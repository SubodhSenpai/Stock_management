import { Badge } from "@/components/ui";
import { cn } from "@/lib/cn";
import { STATUS_STYLES } from "@/lib/config/status";
import type { OperationStatus } from "@/types/api";

/** A document's status, coloured from the one status table. */
export function StatusBadge({ status }: { status: OperationStatus }) {
  const style = STATUS_STYLES[status];
  return (
    <Badge className={style.className} title={style.description}>
      {style.label}
    </Badge>
  );
}

/**
 * The stepper at the top right of an Odoo form: Draft › Ready › Done.
 *
 * Steps the document has passed are filled, the current one is highlighted, and the
 * rest are outlined. Cancelled is shown on its own, because it is a way out of the
 * flow rather than a stage within it.
 */
export function StatusStepper({
  status,
  statuses,
}: {
  status: OperationStatus;
  /** The lifecycle for this document type, which differs between the four. */
  statuses: OperationStatus[];
}) {
  if (status === "canceled") {
    return (
      <div className="flex items-center gap-1">
        <StatusBadge status="canceled" />
      </div>
    );
  }

  const flow = statuses.filter((value) => value !== "canceled");
  const currentIndex = flow.indexOf(status);

  return (
    <ol className="flex items-center gap-1" aria-label="Document status">
      {flow.map((step, index) => {
        const style = STATUS_STYLES[step];
        const isCurrent = index === currentIndex;
        const isPast = index < currentIndex;

        return (
          <li key={step}>
            <span
              title={style.description}
              aria-current={isCurrent ? "step" : undefined}
              className={cn(
                "inline-flex items-center rounded px-2.5 py-1 text-xs font-medium transition-colors",
                isCurrent && cn(style.stepperClassName, "text-white"),
                isPast && "bg-brand-100 text-brand-700",
                !isCurrent && !isPast && "bg-canvas text-ink-muted ring-1 ring-inset ring-line",
              )}
            >
              {style.label}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
