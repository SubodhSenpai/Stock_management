"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo } from "react";

/**
 * Keep list filters in the query string.
 *
 * A filtered list is then a link: it can be shared, bookmarked, and survives a refresh
 * or the back button. Keeping the state in the URL also means the page has no second
 * copy of it to fall out of sync.
 */

export type FilterValue = string | number | boolean | string[] | undefined;

export interface UrlFilters {
  get: (key: string) => string | undefined;
  getAll: (key: string) => string[];
  getNumber: (key: string) => number | undefined;
  getBoolean: (key: string) => boolean;
  /** Replace some keys, keeping the rest. Empty values are removed. */
  set: (patch: Record<string, FilterValue>) => void;
  clear: () => void;
  /** True when anything other than `page` is set: drives the "Clear filters" button. */
  readonly active: boolean;
}

const PAGINATION_KEYS = new Set(["page", "cursor"]);

export function useUrlFilters(): UrlFilters {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  const set = useCallback(
    (patch: Record<string, FilterValue>) => {
      const next = new URLSearchParams(params.toString());
      for (const [key, value] of Object.entries(patch)) {
        next.delete(key);
        if (value === undefined || value === "" || value === false) continue;
        if (Array.isArray(value)) {
          for (const item of value) if (item !== "") next.append(key, item);
        } else {
          next.set(key, String(value));
        }
      }
      // Any filter change invalidates the page number: page 4 of a new result set is
      // rarely what the user meant.
      if (Object.keys(patch).some((key) => !PAGINATION_KEYS.has(key))) next.delete("page");

      const query = next.toString();
      // `replace` rather than `push`: typing in a search box should not fill the
      // history stack with one entry per keystroke.
      router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
    },
    [params, pathname, router],
  );

  const clear = useCallback(() => {
    router.replace(pathname, { scroll: false });
  }, [pathname, router]);

  return useMemo(() => {
    const active = [...params.keys()].some((key) => !PAGINATION_KEYS.has(key));
    return {
      get: (key) => params.get(key) ?? undefined,
      getAll: (key) => params.getAll(key),
      getNumber: (key) => {
        const raw = params.get(key);
        if (!raw) return undefined;
        const parsed = Number(raw);
        return Number.isFinite(parsed) ? parsed : undefined;
      },
      getBoolean: (key) => params.get(key) === "true",
      set,
      clear,
      active,
    };
  }, [clear, params, set]);
}
