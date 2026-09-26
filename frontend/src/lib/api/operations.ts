import type {
  Operation,
  OperationStatus,
  OperationSummary,
  OperationType,
  Page,
} from "@/types/api";
import { http, type Query } from "./client";

export interface OperationFilters extends Query {
  type?: OperationType;
  /** Repeatable: `?status=ready&status=waiting`. */
  status?: OperationStatus[];
  warehouse_id?: number;
  location_id?: number;
  partner_id?: number;
  q?: string;
  late?: boolean;
  page?: number;
  page_size?: number;
}

export interface OperationLinePayload {
  product_id: number;
  /** Receipts, deliveries and transfers move a quantity... */
  quantity?: string;
  /** ...adjustments record what was counted instead. Exactly one of the two. */
  counted_quantity?: string;
}

export interface OperationPayload {
  type: OperationType;
  source_location_id?: number;
  dest_location_id?: number;
  partner_id?: number | null;
  delivery_address?: string | null;
  schedule_date?: string;
  responsible_id?: number | null;
  notes?: string | null;
  lines: OperationLinePayload[];
}

export type OperationUpdatePayload = Partial<Omit<OperationPayload, "type">>;

/**
 * Documents and their lifecycle.
 *
 * State changes are commands, not a writable field: there is no `setStatus`. Which of
 * `confirm` / `checkAvailability` / `validate` / `cancel` is legal right now comes back
 * on every document as `allowed_actions`, so the UI never reimplements the state machine.
 */
export const operationApi = {
  list: (filters: OperationFilters = {}) =>
    http.get<Page<OperationSummary>>("/operations", { query: filters }),
  get: (id: number) => http.get<Operation>(`/operations/${id}`),
  create: (payload: OperationPayload) => http.post<Operation>("/operations", payload),
  update: (id: number, payload: OperationUpdatePayload) =>
    http.patch<Operation>(`/operations/${id}`, payload),

  confirm: (id: number) => http.post<Operation>(`/operations/${id}/confirm`),
  checkAvailability: (id: number) =>
    http.post<Operation>(`/operations/${id}/check-availability`),
  validate: (id: number) => http.post<Operation>(`/operations/${id}/validate`),
  cancel: (id: number) => http.post<Operation>(`/operations/${id}/cancel`),
};
