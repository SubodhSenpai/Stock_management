"use client";

import { forwardRef, type InputHTMLAttributes, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

/**
 * Form controls in the Odoo style: an underlined value rather than a boxed input.
 *
 * `invalid` turns the underline red; it is set from the Field wrapper's aria state so
 * the visual cue and the announced one cannot disagree.
 */

const INVALID = "border-rose-500 focus:border-rose-500";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  invalid?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { invalid, className, ...props },
  ref,
) {
  return (
    <input
      ref={ref}
      className={cn("odoo-input", invalid && INVALID, className)}
      {...props}
    />
  );
});

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  invalid?: boolean;
  /** Shown as a disabled first option when nothing is chosen. */
  placeholder?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { invalid, placeholder, className, children, ...props },
  ref,
) {
  return (
    <select
      ref={ref}
      className={cn("odoo-input cursor-pointer bg-transparent", invalid && INVALID, className)}
      {...props}
    >
      {placeholder !== undefined && <option value="">{placeholder}</option>}
      {children}
    </select>
  );
});

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  invalid?: boolean;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { invalid, className, rows = 3, ...props },
  ref,
) {
  return (
    <textarea
      ref={ref}
      rows={rows}
      className={cn("odoo-input resize-y", invalid && INVALID, className)}
      {...props}
    />
  );
});
