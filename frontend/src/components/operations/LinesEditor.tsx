"use client";

import { useRef } from "react";
import { ProductPicker } from "@/components/common/ProductPicker";
import { Button, Input } from "@/components/ui";
import { cn } from "@/lib/cn";
import type { OperationConfig } from "@/lib/config/operations";
import { formatQuantity } from "@/lib/format";
import type { FieldErrors } from "@/lib/hooks/useForm";
import type { OperationLine, ProductBrief } from "@/types/api";

/**
 * The product lines on a document.
 *
 * Each row is a product and a quantity. Rows the server has reported as short are
 * marked in red with the quantity it could actually meet, which is the mockup's
 * "alert the notification & mark the line red if product is not in stock".
 */

export interface LineDraft {
  /** 0 until a product is chosen. */
  product_id: number;
  quantity: string;
}

export function LinesEditor({
  lines,
  products,
  config,
  sourceLocationId,
  errors,
  availability,
  disabled = false,
  onChange,
}: {
  lines: LineDraft[];
  /** Labels for the chosen products, kept beside the values rather than inside them. */
  products: Record<number, ProductBrief>;
  config: OperationConfig;
  sourceLocationId?: number | null;
  errors: FieldErrors;
  /** Per-line availability from the last server response, keyed by product id. */
  availability?: Map<number, OperationLine>;
  disabled?: boolean;
  onChange: (lines: LineDraft[], products: Record<number, ProductBrief>) => void;
}) {
  const lastQuantityInput = useRef<HTMLInputElement>(null);

  const isCounted = config.quantityField === "counted_quantity";
  const quantityHeader = isCounted ? "Counted Quantity" : "Quantity";

  const update = (index: number, patch: Partial<LineDraft>, product?: ProductBrief) => {
    const next = lines.map((line, position) =>
      position === index ? { ...line, ...patch } : line,
    );
    onChange(next, product ? { ...products, [product.id]: product } : products);
  };

  const addRow = () => {
    onChange([...lines, { product_id: 0, quantity: isCounted ? "0" : "1" }], products);
  };

  const removeRow = (index: number) => {
    onChange(
      lines.filter((_, position) => position !== index),
      products,
    );
  };

  return (
    <section className="mt-6">
      <h2 className="border-b border-line pb-2 text-sm font-semibold uppercase tracking-wide text-brand-700">
        Products
      </h2>

      <div className="scrollbar-slim overflow-x-auto">
        <table className="w-full min-w-[34rem] border-collapse text-sm">
          <thead>
            <tr className="border-b border-line text-xs uppercase tracking-wide text-ink-muted">
              <th scope="col" className="py-2 pr-3 text-left font-medium">
                Product
              </th>
              <th scope="col" className="w-36 py-2 px-3 text-right font-medium">
                {quantityHeader}
              </th>
              {!isCounted && (
                <th scope="col" className="w-32 py-2 px-3 text-right font-medium">
                  Available
                </th>
              )}
              {!disabled && <th scope="col" className="w-10 py-2" />}
            </tr>
          </thead>

          <tbody>
            {lines.map((line, index) => {
              const product = products[line.product_id];
              const productError = errors[`lines[${index}].product_id`];
              const quantityError = errors[`lines[${index}].quantity`];
              const status = availability?.get(line.product_id);
              const isShort = status ? !status.is_available : false;

              return (
                <tr
                  key={index}
                  className={cn(
                    "border-b border-line/70 align-top",
                    isShort && "bg-rose-50/60",
                  )}
                >
                  <td className="py-2 pr-3">
                    <ProductPicker
                      value={product ?? null}
                      locationId={sourceLocationId}
                      disabled={disabled}
                      invalid={Boolean(productError)}
                      onSelect={(chosen) => update(index, { product_id: chosen.id }, chosen)}
                    />
                    {productError && (
                      <p role="alert" className="mt-1 text-xs text-rose-600">
                        {productError}
                      </p>
                    )}
                  </td>

                  <td className="py-2 px-3">
                    <Input
                      ref={index === lines.length - 1 ? lastQuantityInput : undefined}
                      value={line.quantity}
                      disabled={disabled}
                      invalid={Boolean(quantityError)}
                      inputMode="decimal"
                      aria-label={`${quantityHeader} for line ${index + 1}`}
                      className="odoo-input text-right"
                      onChange={(event) => update(index, { quantity: event.target.value })}
                      onKeyDown={(event) => {
                        // Enter on the last row adds another, so a long document can be
                        // typed without reaching for the mouse.
                        if (event.key === "Enter") {
                          event.preventDefault();
                          if (index === lines.length - 1) addRow();
                        }
                      }}
                    />
                    {quantityError && (
                      <p role="alert" className="mt-1 text-right text-xs text-rose-600">
                        {quantityError}
                      </p>
                    )}
                  </td>

                  {!isCounted && (
                    <td className="py-2 px-3 text-right">
                      {status ? (
                        <span
                          className={cn(
                            "text-sm",
                            isShort ? "font-medium text-rose-700" : "text-emerald-700",
                          )}
                          title={
                            isShort
                              ? `Only ${formatQuantity(status.available_quantity)} can be met from this location`
                              : "Enough free stock at this location"
                          }
                        >
                          {formatQuantity(status.available_quantity)}
                        </span>
                      ) : (
                        <span className="text-xs text-ink-muted">—</span>
                      )}
                    </td>
                  )}

                  {!disabled && (
                    <td className="py-2 text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        aria-label={`Remove line ${index + 1}`}
                        disabled={lines.length === 1}
                        onClick={() => removeRow(index)}
                      >
                        ✕
                      </Button>
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {errors.lines && (
        <p role="alert" className="mt-2 text-xs text-rose-600">
          {errors.lines}
        </p>
      )}

      {!disabled && (
        <Button variant="link" className="mt-3 text-sm" onClick={addRow}>
          Add a product
        </Button>
      )}
    </section>
  );
}
