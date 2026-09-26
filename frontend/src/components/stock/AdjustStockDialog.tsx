"use client";

import { Button, Field, Input, Modal } from "@/components/ui";
import { isApiError, messageOf, stockApi } from "@/lib/api";
import { formatQuantity, productLabel } from "@/lib/format";
import { useForm } from "@/lib/hooks/useForm";
import { useToast } from "@/providers/ToastProvider";
import { stockAdjustSchema } from "@/lib/validation/schemas";
import type { StockRow } from "@/types/api";
import { useState } from "react";
import { FormAlert } from "@/components/auth/FormAlert";

/**
 * Record a physical count for one product at one location.
 *
 * The user enters what they counted, not a difference: the server works out the delta
 * and writes it as an adjustment document, so the ledger still explains where the units
 * came from or went. A count below what is already reserved is refused, which is why
 * the reserved figure is shown here.
 */
export function AdjustStockDialog({
  row,
  onClose,
  onAdjusted,
}: {
  row: StockRow;
  onClose: () => void;
  onAdjusted: () => void;
}) {
  const { notify } = useToast();
  const [formError, setFormError] = useState<string>();

  const form = useForm({
    schema: stockAdjustSchema,
    // The caller keys this component by row, so a new row mounts a fresh form rather
    // than carrying the previous product's count over.
    initialValues: { counted_quantity: String(row.on_hand) },
    onSubmit: async (values, helpers) => {
      setFormError(undefined);
      try {
        const operation = await stockApi.adjust({
          product_id: row.product.id,
          location_id: row.location.id,
          counted_quantity: values.counted_quantity,
        });
        notify("success", `Stock updated (${operation.reference})`);
        onAdjusted();
      } catch (error) {
        const unplaced = isApiError(error) ? helpers.applyServerErrors(error) : [];
        setFormError(unplaced[0] ?? messageOf(error));
      }
    },
  });

  const counted = String(form.values.counted_quantity ?? "");
  const difference = Number(counted) - Number(row.on_hand);
  const validDifference = counted !== "" && Number.isFinite(difference);

  return (
    <Modal
      open
      title="Update stock"
      description={`${productLabel(row.product)} at ${row.location.code}`}
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose} disabled={form.submitting}>
            Cancel
          </Button>
          <Button
            variant="primary"
            loading={form.submitting}
            onClick={(event) => form.handleSubmit(event)}
          >
            Apply
          </Button>
        </>
      }
    >
      <form onSubmit={form.handleSubmit} noValidate className="space-y-4">
        <FormAlert message={formError} />

        <dl className="grid grid-cols-2 gap-3 rounded border border-line bg-canvas px-3 py-2 text-sm">
          <div>
            <dt className="text-xs uppercase tracking-wide text-ink-muted">On hand</dt>
            <dd className="font-medium">{formatQuantity(row.on_hand)}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-ink-muted">Reserved</dt>
            <dd className="font-medium">{formatQuantity(row.reserved)}</dd>
          </div>
        </dl>

        <Field
          label="Counted quantity"
          error={form.errorFor("counted_quantity")}
          hint="What you physically counted, not the difference"
          required
        >
          {(aria) => (
            <Input
              {...aria}
              {...form.field("counted_quantity")}
              inputMode="decimal"
              autoFocus
              className="odoo-input text-lg"
            />
          )}
        </Field>

        {validDifference && difference !== 0 && (
          <p className="text-sm text-ink-muted">
            This records a{" "}
            <span className={difference > 0 ? "text-emerald-700" : "text-rose-700"}>
              {difference > 0 ? "gain" : "loss"} of {formatQuantity(String(Math.abs(difference)))}
            </span>{" "}
            as an inventory adjustment.
          </p>
        )}

        {/* Lets Enter submit the form even though the button lives in the modal footer. */}
        <button type="submit" className="hidden" aria-hidden tabIndex={-1} />
      </form>
    </Modal>
  );
}
