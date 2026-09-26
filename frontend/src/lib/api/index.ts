/**
 * The whole API surface, in one import.
 *
 * Components use these modules and never call `fetch` themselves, which keeps cookie
 * handling, token refresh and the error contract in exactly one place.
 */
export { API_BASE_URL, http } from "./client";
export { ApiError, isApiError, messageOf } from "./errors";

export { authApi } from "./auth";
export { catalogApi } from "./catalog";
export { locationApi, partnerApi, warehouseApi } from "./places";
export { operationApi } from "./operations";
export { dashboardApi, stockApi } from "./stock";

export type * from "./auth";
export type * from "./catalog";
export type * from "./operations";
export type * from "./places";
export type * from "./stock";
