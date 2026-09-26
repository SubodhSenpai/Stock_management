import type { MoveDirection, OperationStatus } from "@/types/api";

/**
 * How a status looks and what it means.
 *
 * The colours are the ones from the mockup; the descriptions are used as tooltips so a
 * reviewer who has never seen the app can tell Waiting from Draft without guessing.
 */

export interface StatusStyle {
  label: string;
  /** Tailwind classes for the badge. */
  className: string;
  /** Fill for the status stepper segment. */
  stepperClassName: string;
  description: string;
}

export const STATUS_STYLES: Record<OperationStatus, StatusStyle> = {
  draft: {
    label: "Draft",
    className: "bg-slate-100 text-slate-700 ring-slate-300",
    stepperClassName: "bg-slate-500",
    description: "Still being prepared; nothing is reserved yet.",
  },
  waiting: {
    label: "Waiting",
    className: "bg-amber-100 text-amber-800 ring-amber-300",
    stepperClassName: "bg-amber-500",
    description: "Not enough free stock; it becomes Ready as soon as stock arrives.",
  },
  ready: {
    label: "Ready",
    className: "bg-sky-100 text-sky-800 ring-sky-300",
    stepperClassName: "bg-sky-500",
    description: "Stock is reserved and the document can be validated.",
  },
  done: {
    label: "Done",
    className: "bg-emerald-100 text-emerald-800 ring-emerald-300",
    stepperClassName: "bg-emerald-600",
    description: "Stock has moved and the ledger entry is written.",
  },
  canceled: {
    label: "Cancelled",
    className: "bg-rose-100 text-rose-700 ring-rose-300",
    stepperClassName: "bg-rose-500",
    description: "Abandoned; any reservation was released.",
  },
};

/** Incoming stock reads green, outgoing red, internal blue, as in the mockup. */
export const DIRECTION_STYLES: Record<MoveDirection, { label: string; className: string }> = {
  in: { label: "In", className: "text-emerald-700" },
  out: { label: "Out", className: "text-rose-700" },
  internal: { label: "Internal", className: "text-sky-700" },
};

/** Statuses a document can still be acted on from. */
export const OPEN_STATUSES: OperationStatus[] = ["draft", "waiting", "ready"];
