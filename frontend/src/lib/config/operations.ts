import type { OperationStatus, OperationType } from "@/types/api";

/**
 * The four document types, described as data.
 *
 * Receipts, deliveries, transfers and adjustments are one engine on the backend, so
 * they are one screen here: `OperationList`, `OperationForm` and `OperationDetail` read
 * this table instead of branching on the type. Adding a fifth document type would mean
 * adding a row, not another copy of the page.
 */

/** The segment used in URLs, e.g. `/operations/receipts`. */
export type OperationSlug = "receipts" | "deliveries" | "transfers" | "adjustments";

export interface OperationConfig {
  slug: OperationSlug;
  /** The `type` the API uses. */
  api: OperationType;
  title: string;
  singular: string;
  /** Label for the counterparty field, or null when the type has none. */
  partnerLabel: string | null;
  /** Which kind of partner may be picked. */
  partnerType: "vendor" | "customer" | null;
  /** Whether the user picks the source location, the destination, or both. */
  locations: { source: string | null; destination: string | null };
  /** Statuses this type can reach, in lifecycle order: drives the kanban columns. */
  statuses: OperationStatus[];
  /** Adjustments record a counted quantity; everything else moves a quantity. */
  quantityField: "quantity" | "counted_quantity";
  /** "Validate" on a transfer, "Apply" on an adjustment. */
  validateLabel: string;
  emptyHint: string;
}

export const OPERATION_CONFIGS: Record<OperationSlug, OperationConfig> = {
  receipts: {
    slug: "receipts",
    api: "receipt",
    title: "Receipts",
    singular: "Receipt",
    partnerLabel: "Receive From",
    partnerType: "vendor",
    locations: { source: null, destination: "Destination" },
    statuses: ["draft", "ready", "done", "canceled"],
    quantityField: "quantity",
    validateLabel: "Validate",
    emptyHint: "Record goods arriving from a vendor.",
  },
  deliveries: {
    slug: "deliveries",
    api: "delivery",
    title: "Delivery Orders",
    singular: "Delivery",
    partnerLabel: "Customer",
    partnerType: "customer",
    locations: { source: "Ship From", destination: null },
    statuses: ["draft", "waiting", "ready", "done", "canceled"],
    quantityField: "quantity",
    validateLabel: "Validate",
    emptyHint: "Ship goods out to a customer.",
  },
  transfers: {
    slug: "transfers",
    api: "internal",
    title: "Internal Transfers",
    singular: "Transfer",
    partnerLabel: null,
    partnerType: null,
    locations: { source: "From", destination: "To" },
    statuses: ["draft", "waiting", "ready", "done", "canceled"],
    quantityField: "quantity",
    validateLabel: "Validate",
    emptyHint: "Move stock between two locations.",
  },
  adjustments: {
    slug: "adjustments",
    api: "adjustment",
    title: "Inventory Adjustments",
    singular: "Adjustment",
    partnerLabel: null,
    partnerType: null,
    locations: { source: "Location", destination: null },
    // An adjustment has nothing to reserve, so it applies straight from draft.
    statuses: ["draft", "done", "canceled"],
    quantityField: "counted_quantity",
    validateLabel: "Apply",
    emptyHint: "Correct the books after a physical count.",
  },
};

export const OPERATION_SLUGS = Object.keys(OPERATION_CONFIGS) as OperationSlug[];

export function isOperationSlug(value: string): value is OperationSlug {
  return value in OPERATION_CONFIGS;
}

/** The URL segment for a document, used to link from search results and the ledger. */
const SLUG_BY_TYPE: Record<OperationType, OperationSlug> = {
  receipt: "receipts",
  delivery: "deliveries",
  internal: "transfers",
  adjustment: "adjustments",
};

export function slugForType(type: OperationType): OperationSlug {
  return SLUG_BY_TYPE[type];
}

export function configForType(type: OperationType): OperationConfig {
  return OPERATION_CONFIGS[slugForType(type)];
}

/** Path to one document, whichever list the user came from. */
export function operationHref(type: OperationType, id: number): string {
  return `/operations/${slugForType(type)}/${id}`;
}
