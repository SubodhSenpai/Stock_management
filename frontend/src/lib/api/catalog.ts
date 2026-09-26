import type {
  Category,
  MessageResponse,
  Page,
  Product,
  ProductLocationStock,
  ProductWithStock,
  ReorderRule,
  Uom,
} from "@/types/api";
import { http, type Query } from "./client";

export interface ProductFilters extends Query {
  q?: string;
  category_id?: number;
  warehouse_id?: number;
  include_archived?: boolean;
  page?: number;
  page_size?: number;
}

export interface ProductPayload {
  sku: string;
  name: string;
  category_id: number;
  uom_id: number;
  unit_cost: string;
  initial_stock?: { location_id: number; quantity: string } | null;
}

export interface ProductUpdatePayload {
  name?: string;
  category_id?: number;
  uom_id?: number;
  unit_cost?: string;
  is_active?: boolean;
}

export interface ReorderRulePayload {
  product_id: number;
  warehouse_id: number;
  min_quantity: string;
  max_quantity: string;
}

/** Products, their categories and units, and the reordering rules that flag low stock. */
export const catalogApi = {
  listProducts: (filters: ProductFilters = {}) =>
    http.get<Page<ProductWithStock>>("/products", { query: filters }),
  getProduct: (id: number) => http.get<Product>(`/products/${id}`),
  createProduct: (payload: ProductPayload) => http.post<Product>("/products", payload),
  updateProduct: (id: number, payload: ProductUpdatePayload) =>
    http.patch<Product>(`/products/${id}`, payload),
  archiveProduct: (id: number) => http.delete<MessageResponse>(`/products/${id}`),
  productStock: (id: number) =>
    http.get<ProductLocationStock[]>(`/products/${id}/stock`),

  listCategories: () => http.get<Category[]>("/categories"),
  createCategory: (name: string) => http.post<Category>("/categories", { name }),
  deleteCategory: (id: number) => http.delete<MessageResponse>(`/categories/${id}`),

  listUoms: () => http.get<Uom[]>("/uoms"),

  listReorderRules: (filters: { product_id?: number; warehouse_id?: number } = {}) =>
    http.get<ReorderRule[]>("/reorder-rules", { query: filters }),
  createReorderRule: (payload: ReorderRulePayload) =>
    http.post<ReorderRule>("/reorder-rules", payload),
  updateReorderRule: (id: number, payload: Partial<ReorderRulePayload>) =>
    http.patch<ReorderRule>(`/reorder-rules/${id}`, payload),
  deleteReorderRule: (id: number) => http.delete<MessageResponse>(`/reorder-rules/${id}`),
};
