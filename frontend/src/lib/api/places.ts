import type {
  Location,
  LocationType,
  MessageResponse,
  Page,
  Partner,
  PartnerType,
  Warehouse,
} from "@/types/api";
import { http } from "./client";

export interface WarehousePayload {
  name: string;
  short_code: string;
  address: string | null;
}

export interface LocationPayload {
  name: string;
  short_code: string;
  warehouse_id: number;
}

export interface PartnerPayload {
  name: string;
  type: PartnerType;
  email: string | null;
  phone: string | null;
  address: string | null;
}

/** Warehouses and the locations inside them. Writing requires the manager role. */
export const warehouseApi = {
  list: (includeArchived = false) =>
    http.get<Warehouse[]>("/warehouses", { query: { include_archived: includeArchived } }),
  get: (id: number) => http.get<Warehouse>(`/warehouses/${id}`),
  create: (payload: WarehousePayload) => http.post<Warehouse>("/warehouses", payload),
  update: (id: number, payload: Partial<Omit<WarehousePayload, "short_code">>) =>
    http.patch<Warehouse>(`/warehouses/${id}`, payload),
  archive: (id: number) => http.delete<MessageResponse>(`/warehouses/${id}`),
};

export const locationApi = {
  list: (filters: { warehouse_id?: number; type?: LocationType; include_archived?: boolean } = {}) =>
    http.get<Location[]>("/locations", { query: filters }),
  create: (payload: LocationPayload) => http.post<Location>("/locations", payload),
  update: (id: number, payload: { name?: string; is_active?: boolean }) =>
    http.patch<Location>(`/locations/${id}`, payload),
  archive: (id: number) => http.delete<MessageResponse>(`/locations/${id}`),
};

/** Vendors and customers: the counterparties on receipts and deliveries. */
export const partnerApi = {
  list: (filters: { q?: string; type?: PartnerType; page?: number; page_size?: number } = {}) =>
    http.get<Page<Partner>>("/partners", { query: filters }),
  get: (id: number) => http.get<Partner>(`/partners/${id}`),
  create: (payload: PartnerPayload) => http.post<Partner>("/partners", payload),
  update: (id: number, payload: Partial<PartnerPayload>) =>
    http.patch<Partner>(`/partners/${id}`, payload),
};
