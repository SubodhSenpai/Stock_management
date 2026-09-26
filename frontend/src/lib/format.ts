import type { Decimal } from "@/types/api";

/**
 * Display helpers.
 *
 * Everything here is one-way: values are formatted for the screen and never fed back
 * into a request. Quantities stay strings on the wire so the exact decimal the database
 * holds is the one that comes back.
 */

/** Parse an API decimal for arithmetic or comparison. Display-only. */
export function toNumber(value: Decimal | number | null | undefined): number {
  if (value === null || value === undefined) return 0;
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

/** Trim trailing zeros so `"50.000"` reads as `50` but `"0.500"` keeps its half. */
export function formatQuantity(value: Decimal | number | null | undefined): string {
  const amount = toNumber(value);
  return amount.toLocaleString("en-IN", { maximumFractionDigits: 3 });
}

export function formatMoney(value: Decimal | number | null | undefined): string {
  return `₹${toNumber(value).toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

const DATE_FORMAT: Intl.DateTimeFormatOptions = {
  day: "2-digit",
  month: "short",
  year: "numeric",
};

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleDateString("en-IN", DATE_FORMAT);
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString("en-IN", {
    ...DATE_FORMAT,
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** `YYYY-MM-DD` in the user's own timezone, for `<input type="date">` defaults. */
export function todayIso(): string {
  const now = new Date();
  const offsetMinutes = now.getTimezoneOffset();
  return new Date(now.getTime() - offsetMinutes * 60_000).toISOString().slice(0, 10);
}

export function productLabel(product: { sku: string; name: string }): string {
  return `[${product.sku}] ${product.name}`;
}

export function userLabel(user: { full_name: string | null; login_id: string }): string {
  return user.full_name?.trim() || user.login_id;
}

/** Initials for the avatar in the top bar. */
export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  const first = parts[0]?.[0] ?? "";
  const last = parts.length > 1 ? (parts[parts.length - 1]?.[0] ?? "") : "";
  return (first + last).toUpperCase();
}

export function pluralise(count: number, singular: string, plural = `${singular}s`): string {
  return `${count} ${count === 1 ? singular : plural}`;
}
