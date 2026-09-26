import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/cn";
import { Spinner } from "./Spinner";

/**
 * The one button.
 *
 * `primary` is the teal action on an Odoo form ("Validate", "Save"), `secondary` the
 * outlined one beside it, `ghost` the flat one used in toolbars, and `danger` for
 * cancelling a document. A button that is `loading` is also disabled, so a slow request
 * cannot be submitted twice.
 */

type Variant = "primary" | "secondary" | "ghost" | "danger" | "link";
type Size = "sm" | "md";

const VARIANTS: Record<Variant, string> = {
  primary:
    "bg-accent-500 text-white border border-accent-500 hover:bg-accent-600 hover:border-accent-600",
  secondary:
    "bg-white text-ink border border-line-strong hover:bg-brand-50 hover:border-brand-400",
  ghost: "bg-transparent text-ink border border-transparent hover:bg-brand-50",
  danger: "bg-white text-rose-700 border border-rose-300 hover:bg-rose-50",
  link: "bg-transparent text-accent-600 border border-transparent hover:underline p-0",
};

const SIZES: Record<Size, string> = {
  sm: "text-xs px-2.5 py-1.5",
  md: "text-sm px-3.5 py-2",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  icon?: ReactNode;
}

export function Button({
  variant = "secondary",
  size = "md",
  loading = false,
  icon,
  className,
  disabled,
  children,
  type = "button",
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(
        "inline-flex items-center justify-center gap-1.5 rounded font-medium transition-colors",
        "disabled:cursor-not-allowed disabled:opacity-50",
        variant !== "link" && SIZES[size],
        VARIANTS[variant],
        className,
      )}
      {...props}
    >
      {loading ? <Spinner size={size === "sm" ? 12 : 14} /> : icon}
      {children}
    </button>
  );
}
