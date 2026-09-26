"use client";

import { useCallback, useMemo, useState, type ChangeEvent, type SyntheticEvent } from "react";
import type { z } from "zod";
import type { ApiError } from "@/lib/api";

/** Any control that reports its value through `event.target.value`. */
type FormControl = HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement;

/**
 * What `field(name)` returns: spread it onto an input, select or textarea.
 *
 * Exported so a shared field set can state which fields it needs without depending on
 * the schema behind them.
 */
export interface FieldProps {
  name: string;
  value: string;
  invalid: boolean;
  onChange: (event: ChangeEvent<FormControl>) => void;
}

/**
 * A small form controller driven by a Zod schema.
 *
 * Written rather than pulled in, for the same reason the backend writes its own auth:
 * the behaviour needed here is narrow, and owning it keeps the dependency list short
 * enough to audit. It does three things — hold values, run the schema on submit, and
 * place server-side field errors next to the right input.
 *
 * Field paths are normalised to the shape the API already uses (`lines[0].quantity`),
 * so a Zod issue and a Pydantic detail address the same input.
 */

export type FieldErrors = Record<string, string>;

/** `["lines", 0, "quantity"]` -> `"lines[0].quantity"`, matching the server's format. */
export function pathToField(path: ReadonlyArray<string | number>): string {
  return path.reduce<string>((acc, part) => {
    if (typeof part === "number") return `${acc}[${part}]`;
    return acc ? `${acc}.${part}` : part;
  }, "");
}

/**
 * Passed to `onSubmit` so a handler can report a failed request without reaching back
 * for the controller it is being defined inside.
 */
export interface SubmitHelpers {
  /** Place a server's `details` onto the matching inputs; returns what had no field. */
  applyServerErrors: (error: ApiError) => string[];
  setErrors: (errors: FieldErrors) => void;
}

interface UseFormOptions<TSchema extends z.ZodTypeAny> {
  schema: TSchema;
  initialValues: z.input<TSchema>;
  onSubmit: (values: z.output<TSchema>, helpers: SubmitHelpers) => Promise<void> | void;
}

export interface FormController<TSchema extends z.ZodTypeAny> {
  values: z.input<TSchema>;
  errors: FieldErrors;
  submitting: boolean;
  setValue: <K extends keyof z.input<TSchema>>(name: K, value: z.input<TSchema>[K]) => void;
  setValues: (values: Partial<z.input<TSchema>>) => void;
  /**
   * Props for a controlled input, select or textarea: spread them onto the control and
   * pass `errorFor(name)` to the surrounding Field.
   */
  field: (name: keyof z.input<TSchema> & string) => FieldProps;
  errorFor: (field: string) => string | undefined;
  clearError: (field: string) => void;
  /** Place a server's `details` onto the matching inputs. Returns what it could not place. */
  applyServerErrors: (error: ApiError) => string[];
  handleSubmit: (event: SyntheticEvent) => void;
  reset: (values?: z.input<TSchema>) => void;
}

export function useForm<TSchema extends z.ZodTypeAny>({
  schema,
  initialValues,
  onSubmit,
}: UseFormOptions<TSchema>): FormController<TSchema> {
  const [values, setAll] = useState<z.input<TSchema>>(initialValues);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [submitting, setSubmitting] = useState(false);

  const clearError = useCallback((field: string) => {
    setErrors((current) => {
      if (!(field in current)) return current;
      const next = { ...current };
      delete next[field];
      return next;
    });
  }, []);

  const setValue = useCallback(
    <K extends keyof z.input<TSchema>>(name: K, value: z.input<TSchema>[K]) => {
      setAll((current) => ({ ...current, [name]: value }));
      clearError(String(name));
    },
    [clearError],
  );

  const setValues = useCallback((patch: Partial<z.input<TSchema>>) => {
    setAll((current) => ({ ...current, ...patch }));
  }, []);

  const applyServerErrors = useCallback((error: ApiError) => {
    const placed: FieldErrors = {};
    const unplaced: string[] = [];
    for (const detail of error.details) {
      if (detail.field) placed[detail.field] ??= detail.message;
      else unplaced.push(detail.message);
    }
    setErrors(placed);
    return unplaced;
  }, []);

  const handleSubmit = useCallback(
    (event: SyntheticEvent) => {
      event.preventDefault();
      const result = schema.safeParse(values);
      if (!result.success) {
        const found: FieldErrors = {};
        for (const issue of result.error.issues) {
          const key = pathToField(issue.path);
          found[key] ??= issue.message;
        }
        setErrors(found);
        return;
      }
      setErrors({});
      setSubmitting(true);
      void Promise.resolve(
        onSubmit(result.data as z.output<TSchema>, { applyServerErrors, setErrors }),
      ).finally(() => setSubmitting(false));
    },
    [applyServerErrors, onSubmit, schema, values],
  );

  const field = useCallback(
    (name: keyof z.input<TSchema> & string) => ({
      name,
      value: String((values as Record<string, unknown>)[name] ?? ""),
      invalid: Boolean(errors[name]),
      onChange: (event: ChangeEvent<FormControl>) =>
        setValue(name, event.target.value as z.input<TSchema>[typeof name]),
    }),
    [errors, setValue, values],
  );

  const reset = useCallback(
    (next?: z.input<TSchema>) => {
      setAll(next ?? initialValues);
      setErrors({});
    },
    [initialValues],
  );

  return useMemo(
    () => ({
      values,
      errors,
      submitting,
      setValue,
      setValues,
      field,
      errorFor: (name: string) => errors[name],
      clearError,
      applyServerErrors,
      handleSubmit,
      reset,
    }),
    [
      applyServerErrors,
      clearError,
      errors,
      field,
      handleSubmit,
      reset,
      setValue,
      setValues,
      submitting,
      values,
    ],
  );
}
