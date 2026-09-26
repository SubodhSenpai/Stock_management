"use client";

import { useEffect, useId, useRef, useState } from "react";
import { Spinner } from "@/components/ui";
import { catalogApi } from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatQuantity, productLabel } from "@/lib/format";
import { useDebouncedValue } from "@/lib/hooks/useDebouncedValue";
import { useOnClickOutside } from "@/lib/hooks/useOnClickOutside";
import type { ProductBrief, ProductWithStock } from "@/types/api";

/**
 * Pick a product by typing.
 *
 * The catalogue can be large, so this searches the server rather than loading every
 * product into a `<select>`. Free stock is shown beside each result at the location
 * the document works from, which is what stops a user picking something they will only
 * be told is short two steps later.
 */
export function ProductPicker({
  value,
  onSelect,
  locationId,
  invalid,
  disabled,
  id,
  "aria-describedby": describedBy,
}: {
  value: ProductBrief | null;
  onSelect: (product: ProductWithStock) => void;
  /** Narrows the free-stock figure to the location this document draws from. */
  locationId?: number | null;
  invalid?: boolean;
  disabled?: boolean;
  id?: string;
  "aria-describedby"?: string;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ProductWithStock[]>([]);
  const [loading, setLoading] = useState(false);
  const [highlight, setHighlight] = useState(0);

  const container = useRef<HTMLDivElement>(null);
  const debounced = useDebouncedValue(query, 250);
  useOnClickOutside(container, () => setOpen(false), open);

  // The combobox has to name the list it controls for assistive technology to follow it.
  const generatedId = useId();
  const listboxId = `${generatedId}-listbox`;

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoading(true);

    catalogApi
      .listProducts({ q: debounced || undefined, page_size: 20 })
      .then((page) => {
        if (cancelled) return;
        setResults(page.items);
        setHighlight(0);
      })
      .catch(() => {
        // A failed lookup shows "no matches" rather than an alert: the user is still
        // typing, and the submit will report the real problem if there is one.
        if (!cancelled) setResults([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [debounced, open]);

  const choose = (product: ProductWithStock) => {
    onSelect(product);
    setOpen(false);
    setQuery("");
  };

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (!open) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setHighlight((index) => Math.min(index + 1, results.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlight((index) => Math.max(index - 1, 0));
    } else if (event.key === "Enter") {
      const product = results[highlight];
      if (product) {
        event.preventDefault();
        choose(product);
      }
    }
  };

  return (
    <div ref={container} className="relative">
      <input
        id={id}
        aria-describedby={describedBy}
        role="combobox"
        aria-expanded={open}
        aria-controls={listboxId}
        aria-autocomplete="list"
        aria-invalid={invalid || undefined}
        disabled={disabled}
        value={open ? query : value ? productLabel(value) : ""}
        placeholder={value ? productLabel(value) : "Search a product..."}
        onChange={(event) => {
          setQuery(event.target.value);
          if (!open) setOpen(true);
        }}
        onFocus={() => !disabled && setOpen(true)}
        onKeyDown={handleKeyDown}
        className={cn("odoo-input", invalid && "border-rose-500")}
      />

      {open && !disabled && (
        <ul
          id={listboxId}
          role="listbox"
          aria-label="Product search results"
          className="absolute z-30 mt-1 max-h-64 w-full min-w-[18rem] overflow-y-auto rounded border border-line bg-sheet py-1 shadow-lg"
        >
          {loading && (
            <li className="flex items-center gap-2 px-3 py-2 text-xs text-ink-muted">
              <Spinner size={12} /> Searching...
            </li>
          )}

          {!loading && results.length === 0 && (
            <li className="px-3 py-2 text-xs text-ink-muted">No products match that.</li>
          )}

          {!loading &&
            results.map((product, index) => (
              <li key={product.id}>
                <button
                  type="button"
                  role="option"
                  aria-selected={index === highlight}
                  onMouseEnter={() => setHighlight(index)}
                  onClick={() => choose(product)}
                  className={cn(
                    "flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm",
                    index === highlight ? "bg-brand-50" : "hover:bg-brand-50/60",
                  )}
                >
                  <span className="min-w-0">
                    <span className="block truncate font-medium text-ink">{product.name}</span>
                    <span className="block font-mono text-xs text-ink-muted">{product.sku}</span>
                  </span>
                  <span
                    className={cn(
                      "shrink-0 text-xs",
                      Number(product.free_to_use) > 0 ? "text-emerald-700" : "text-rose-600",
                    )}
                  >
                    {formatQuantity(product.free_to_use)} free
                  </span>
                </button>
              </li>
            ))}

          {locationId && (
            <li className="border-t border-line px-3 py-1.5 text-[11px] text-ink-muted">
              Free quantities are across all locations; the document checks the one it
              ships from.
            </li>
          )}
        </ul>
      )}
    </div>
  );
}
