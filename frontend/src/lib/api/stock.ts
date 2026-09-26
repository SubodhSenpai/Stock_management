import type {
  CursorPage,
  DashboardSummary,
  LowStockItem,
  Operation,
  Page,
  StockMove,
  StockRow,
} from "@/types/api";
import { http, type Query } from "./client";

export interface StockFilters extends Query {
  q?: string;
  warehouse_id?: number;
  location_id?: number;
  category_id?: number;
  page?: number;
  page_size?: number;
}

export interface MoveFilters extends Query {
  q?: string;
  product_id?: number;
  location_id?: number;
  warehouse_id?: number;
  date_from?: string;
  date_to?: string;
  cursor?: string | null;
  limit?: number;
}

/**
 * Stock levels and the ledger.
 *
 * `adjust` sets a counted quantity; the backend turns it into an adjustment document,
 * so even a correction leaves a ledger entry explaining the change.
 */
export const stockApi = {
  list: (filters: StockFilters = {}) => http.get<Page<StockRow>>("/stock", { query: filters }),
  adjust: (payload: { product_id: number; location_id: number; counted_quantity: string }) =>
    http.post<Operation>("/stock/adjust", payload),
  /** Cursor-paginated: the ledger only grows, so an offset would slow down every page. */
  moves: (filters: MoveFilters = {}) =>
    http.get<CursorPage<StockMove>>("/moves", { query: filters }),
};

export const dashboardApi = {
  summary: (filters: { warehouse_id?: number; category_id?: number } = {}) =>
    http.get<DashboardSummary>("/dashboard/summary", { query: filters }),
  lowStock: (filters: { warehouse_id?: number; limit?: number } = {}) =>
    http.get<LowStockItem[]>("/dashboard/low-stock", { query: filters }),
};
