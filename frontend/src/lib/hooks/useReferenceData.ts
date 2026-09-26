"use client";

import { locationApi, partnerApi, warehouseApi } from "@/lib/api";
import { useResource } from "./useResource";
import type { Location, Partner, PartnerType, Warehouse } from "@/types/api";

/**
 * The lists every document form needs to fill its dropdowns.
 *
 * Warehouses, internal locations and contacts change rarely and are small, so they are
 * fetched whole rather than searched. Products are the exception and use a picker that
 * queries the server.
 */

/** Internal locations only: the virtual ones are the API's business, not the user's. */
export function useInternalLocations() {
  return useResource<Location[]>(
    () => locationApi.list({ type: "internal" }),
    [],
  );
}

export function useWarehouses() {
  return useResource<Warehouse[]>(() => warehouseApi.list(), []);
}

/**
 * Contacts of the kind this document needs.
 *
 * `both` counts as either, which is why the filter is applied here rather than being
 * assumed from the stored type.
 */
export function usePartners(type: PartnerType | null) {
  return useResource<Partner[]>(
    type
      ? () => partnerApi.list({ type, page_size: 100 }).then((page) => page.items)
      : null,
    [type],
  );
}
