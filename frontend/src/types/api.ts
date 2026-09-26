/**
 * TypeScript mirrors of the backend's Pydantic response models.
 *
 * Quantities and money are typed as `string`, not `number`: the API serialises
 * `Decimal` as a JSON string so that exact values survive the round trip. Parse them
 * with `toNumber` from `@/lib/format` only for display or arithmetic, never for storage.
 */

export type UserRole = "manager" | "staff";
export type LocationType = "internal" | "vendor" | "customer" | "adjustment";
export type OperationType = "receipt" | "delivery" | "internal" | "adjustment";
export type OperationStatus = "draft" | "waiting" | "ready" | "done" | "canceled";
export type PartnerType = "vendor" | "customer" | "both";
export type MoveDirection = "in" | "out" | "internal";
export type OperationAction = "confirm" | "check_availability" | "validate" | "cancel";

/** A decimal value carried as a string, e.g. `"12.500"`. */
export type Decimal = string;

// ---------------------------------------------------------------- envelopes

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

/** Keyset pagination, used by the ledger. `next_cursor` is null on the last page. */
export interface CursorPage<T> {
  items: T[];
  next_cursor: string | null;
}

export interface MessageResponse {
  message: string;
}

export interface ApiErrorDetail {
  field: string;
  message: string;
}

export interface ApiErrorBody {
  code: string;
  message: string;
  details: ApiErrorDetail[];
  request_id: string | null;
}

export interface ApiErrorResponse {
  error: ApiErrorBody;
}

// ---------------------------------------------------------------- identity

export interface User {
  id: number;
  login_id: string;
  email: string;
  full_name: string | null;
  role: UserRole;
  created_at: string;
}

export interface UserBrief {
  id: number;
  login_id: string;
  full_name: string | null;
}

export interface ResetToken {
  reset_token: string;
}

// ---------------------------------------------------------------- catalog

export interface Category {
  id: number;
  name: string;
}

export interface Uom {
  id: number;
  code: string;
  name: string;
  allow_fraction: boolean;
}

export interface ProductBrief {
  id: number;
  sku: string;
  name: string;
}

export interface Product extends ProductBrief {
  category: Category;
  uom: Uom;
  unit_cost: Decimal;
  is_active: boolean;
}

/** A product with its stock totals: the shape returned by `GET /products`. */
export interface ProductWithStock extends Product {
  on_hand: Decimal;
  reserved: Decimal;
  free_to_use: Decimal;
  is_low_stock: boolean;
}

export interface ProductLocationStock {
  location: LocationBrief;
  on_hand: Decimal;
  reserved: Decimal;
  free_to_use: Decimal;
}

export interface ReorderRule {
  id: number;
  product_id: number;
  warehouse_id: number;
  min_quantity: Decimal;
  max_quantity: Decimal;
}

// ---------------------------------------------------------------- places

export interface Warehouse {
  id: number;
  name: string;
  short_code: string;
  address: string | null;
  is_active: boolean;
}

export interface LocationBrief {
  id: number;
  code: string;
  name: string;
  type: LocationType;
}

export interface Location extends LocationBrief {
  short_code: string;
  warehouse_id: number | null;
  is_active: boolean;
}

export interface PartnerBrief {
  id: number;
  name: string;
}

export interface Partner extends PartnerBrief {
  type: PartnerType;
  email: string | null;
  phone: string | null;
  address: string | null;
}

// ---------------------------------------------------------------- stock

export interface StockRow {
  product: ProductBrief;
  location: LocationBrief;
  unit_cost: Decimal;
  on_hand: Decimal;
  reserved: Decimal;
  free_to_use: Decimal;
}

export interface StockMove {
  id: number;
  operation_id: number;
  reference: string;
  product: ProductBrief;
  from_location: LocationBrief;
  to_location: LocationBrief;
  quantity: Decimal;
  direction: MoveDirection;
  contact: string | null;
  moved_at: string;
}

// ---------------------------------------------------------------- operations

export interface OperationLine {
  id: number;
  product: ProductBrief;
  quantity: Decimal | null;
  counted_quantity: Decimal | null;
  system_quantity: Decimal | null;
  available_quantity: Decimal;
  is_available: boolean;
}

export interface OperationSummary {
  id: number;
  reference: string;
  type: OperationType;
  status: OperationStatus;
  source_location: LocationBrief;
  dest_location: LocationBrief;
  partner: PartnerBrief | null;
  schedule_date: string;
  responsible: UserBrief | null;
  created_at: string;
  is_late: boolean;
}

export interface Operation extends OperationSummary {
  warehouse_id: number;
  delivery_address: string | null;
  notes: string | null;
  validated_at: string | null;
  lines: OperationLine[];
  /** Exactly the actions legal right now. The UI renders its buttons from this list. */
  allowed_actions: OperationAction[];
}

// ---------------------------------------------------------------- dashboard

export interface OperationCard {
  type: OperationType;
  to_process: number;
  waiting: number;
  late: number;
  upcoming: number;
  pending: number;
}

export interface LowStockItem {
  product: ProductBrief;
  warehouse_id: number;
  warehouse_name: string;
  on_hand: Decimal;
  min_quantity: Decimal;
  suggested_order: Decimal;
}

export interface DashboardSummary {
  products_in_stock: number;
  out_of_stock: number;
  low_stock: number;
  cards: OperationCard[];
}

// ---------------------------------------------------------------- realtime

export interface OperationChangedEvent {
  type: "operation.changed";
  operations: Array<{
    id: number;
    reference: string;
    operation_type: OperationType;
    status: OperationStatus;
  }>;
}

export interface StockChangedEvent {
  type: "stock.changed";
  product_ids: number[];
  location_ids: number[];
}

export interface LowStockEvent {
  type: "stock.low";
  items: Array<Record<string, unknown>>;
}

export type RealtimeEvent = OperationChangedEvent | StockChangedEvent | LowStockEvent;
export type RealtimeTopic = RealtimeEvent["type"];
