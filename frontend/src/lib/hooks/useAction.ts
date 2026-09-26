"use client";

import { useCallback, useRef, useState } from "react";
import { ApiError, isApiError, messageOf } from "@/lib/api";
import { useToast } from "@/providers/ToastProvider";

/**
 * Run a write and report what happened.
 *
 * Buttons that change something (confirm, validate, cancel, save) all need the same
 * three things: a pending flag so the button can disable itself, a guard against a
 * double click, and one consistent way of surfacing the error. This provides them.
 */

interface ActionOptions<TResult> {
  /** Shown as a success toast. Given the result, so it can name the document. */
  successMessage?: (result: TResult) => string;
  onSuccess?: (result: TResult) => void;
  /** Handle the failure yourself, e.g. to map field errors onto a form. */
  onError?: (error: ApiError) => void;
  /** Off when the caller renders the error inline instead. */
  toastOnError?: boolean;
}

export interface ActionState<TArgs extends unknown[], TResult> {
  run: (...args: TArgs) => Promise<TResult | undefined>;
  pending: boolean;
  error: ApiError | undefined;
  reset: () => void;
}

export function useAction<TArgs extends unknown[], TResult>(
  action: (...args: TArgs) => Promise<TResult>,
  options: ActionOptions<TResult> = {},
): ActionState<TArgs, TResult> {
  const { successMessage, onSuccess, onError, toastOnError = true } = options;
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<ApiError>();
  const { notify } = useToast();
  const inFlight = useRef(false);

  const run = useCallback(
    async (...args: TArgs) => {
      // Validating twice is refused by the server anyway, but a disabled button and an
      // in-flight guard mean the user never sees that error in the first place.
      if (inFlight.current) return undefined;
      inFlight.current = true;
      setPending(true);
      setError(undefined);
      try {
        const result = await action(...args);
        if (successMessage) notify("success", successMessage(result));
        onSuccess?.(result);
        return result;
      } catch (caught) {
        const apiError = isApiError(caught)
          ? caught
          : new ApiError(0, {
              code: "UNEXPECTED_ERROR",
              message: messageOf(caught),
              details: [],
              request_id: null,
            });
        setError(apiError);
        onError?.(apiError);
        if (toastOnError) {
          notify("error", apiError.message, apiError.details[0]?.message);
        }
        return undefined;
      } finally {
        inFlight.current = false;
        setPending(false);
      }
    },
    [action, notify, onError, onSuccess, successMessage, toastOnError],
  );

  return { run, pending, error, reset: () => setError(undefined) };
}
