"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, isApiError } from "@/lib/api";
import { useRealtime } from "@/providers/RealtimeProvider";
import type { RealtimeTopic } from "@/types/api";

/**
 * Load data, and reload it when the server says it changed.
 *
 * Every list and detail screen is built on this, so loading, error and refetch behave
 * the same everywhere and no page writes its own `useEffect` fetch. A request that is
 * superseded is ignored rather than cancelled mid-flight, which keeps a slow response
 * from overwriting a newer one.
 */

export interface ResourceState<T> {
  data: T | undefined;
  error: ApiError | undefined;
  loading: boolean;
  /** True only on the very first load, so a refresh does not flash the skeleton. */
  initialLoading: boolean;
  refetch: () => void;
}

export function useResource<T>(
  /** The fetch to run, or null to stay idle until a dependency is known. */
  fetcher: (() => Promise<T>) | null,
  /** Values that change the request. Same contract as a dependency array. */
  deps: ReadonlyArray<unknown>,
  /** Realtime topics that should trigger a silent reload. */
  topics: RealtimeTopic[] = [],
): ResourceState<T> {
  const [data, setData] = useState<T>();
  const [error, setError] = useState<ApiError>();
  const [loading, setLoading] = useState(fetcher !== null);
  const [loaded, setLoaded] = useState(false);

  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;
  const requestId = useRef(0);

  const load = useCallback(async () => {
    const run = fetcherRef.current;
    if (!run) {
      setLoading(false);
      return;
    }
    const id = ++requestId.current;
    setLoading(true);
    try {
      const result = await run();
      if (id !== requestId.current) return; // A newer request has already started.
      setData(result);
      setError(undefined);
    } catch (caught) {
      if (id !== requestId.current) return;
      setError(isApiError(caught) ? caught : new ApiError(0, {
        code: "UNEXPECTED_ERROR",
        message: caught instanceof Error ? caught.message : "Something went wrong.",
        details: [],
        request_id: null,
      }));
    } finally {
      if (id === requestId.current) {
        setLoading(false);
        setLoaded(true);
      }
    }
    // The fetcher is read from a ref, so the caller's deps are what matters here.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    void load();
  }, [load]);

  useRealtime(topics, () => {
    void load();
  });

  return { data, error, loading, initialLoading: loading && !loaded, refetch: load };
}
