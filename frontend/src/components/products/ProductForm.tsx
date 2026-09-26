"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button, Field, Input, Select } from "@/components/ui";
import { FormSection, FormSheet } from "@/components/operations/FormSheet";
import { catalogApi, isApiError, messageOf } from "@/lib/api";
import { useForm } from "@/lib/hooks/useForm";
import { useInternalLocations } from "@/lib/hooks/useReferenceData";
import { useToast } from "@/providers/ToastProvider";
import { productEditSchema, productSchema } from "@/lib/validation/schemas";
import type { Product } from "@/types/api";
import { ProductFields } from "./ProductFields";

/**
 * Creating a product.
 *
 * An opening balance is optional and is not written straight into the stock table: the
 * backend records it as an adjustment document, so even a product's first units are
 * explained by a ledger entry.
 */
export function ProductCreateForm() {
  const router = useRouter();
  const { notify } = useToast();
  const [formError, setFormError] = useState<string>();
  const locations = useInternalLocations();

  const form = useForm({
    schema: productSchema,
    initialValues: {
      sku: "",
      name: "",
      category_id: "",
      uom_id: "",
      unit_cost: "0.00",
      initial_location_id: "",
      initial_quantity: "",
    },
    onSubmit: async (values, helpers) => {
      setFormError(undefined);
      try {
        const saved = await catalogApi.createProduct({
          sku: values.sku,
          name: values.name,
          category_id: values.category_id,
          uom_id: values.uom_id,
          unit_cost: values.unit_cost,
          initial_stock:
            values.initial_location_id && values.initial_quantity
              ? { location_id: values.initial_location_id, quantity: values.initial_quantity }
              : null,
        });
        notify("success", `${saved.name} created`);
        router.push(`/products/${saved.id}`);
        router.refresh();
      } catch (error) {
        const unplaced = isApiError(error) ? helpers.applyServerErrors(error) : [];
        setFormError(unplaced[0] ?? messageOf(error));
      }
    },
  });

  return (
    <form onSubmit={form.handleSubmit} noValidate>
      <FormSheet
        title="New Product"
        formError={formError}
        actions={<FormActions submitting={form.submitting} onDiscard={() => router.back()} />}
      >
        <ProductFields form={form} />

        <FormSection title="Opening stock (optional)">
          <Field label="Location" error={form.errorFor("initial_location_id")}>
            {(aria) => (
              <Select {...aria} {...form.field("initial_location_id")} placeholder="None">
                {(locations.data ?? []).map((location) => (
                  <option key={location.id} value={location.id}>
                    {location.code}
                  </option>
                ))}
              </Select>
            )}
          </Field>

          <Field
            label="Quantity"
            error={form.errorFor("initial_quantity")}
            hint="Recorded as an inventory adjustment"
          >
            {(aria) => (
              <Input {...aria} {...form.field("initial_quantity")} inputMode="decimal" placeholder="0" />
            )}
          </Field>
        </FormSection>
      </FormSheet>
    </form>
  );
}

/** Editing a product. The SKU is fixed, because past documents already refer to it. */
export function ProductEditForm({ product }: { product: Product }) {
  const router = useRouter();
  const { notify } = useToast();
  const [formError, setFormError] = useState<string>();

  const form = useForm({
    schema: productEditSchema,
    initialValues: {
      sku: product.sku,
      name: product.name,
      category_id: String(product.category.id),
      uom_id: String(product.uom.id),
      unit_cost: String(product.unit_cost),
    },
    onSubmit: async (values, helpers) => {
      setFormError(undefined);
      try {
        // `sku` is only here so the shared field set can display it. The endpoint
        // rejects unknown fields, and it is not one it accepts.
        const { sku: _sku, ...changes } = values;
        const saved = await catalogApi.updateProduct(product.id, changes);
        notify("success", `${saved.name} saved`);
        router.push(`/products/${saved.id}`);
        router.refresh();
      } catch (error) {
        const unplaced = isApiError(error) ? helpers.applyServerErrors(error) : [];
        setFormError(unplaced[0] ?? messageOf(error));
      }
    },
  });

  return (
    <form onSubmit={form.handleSubmit} noValidate>
      <FormSheet
        title={product.name}
        subtitle={product.sku}
        formError={formError}
        actions={<FormActions submitting={form.submitting} onDiscard={() => router.back()} />}
      >
        <ProductFields form={form} skuLocked />
      </FormSheet>
    </form>
  );
}

function FormActions({
  submitting,
  onDiscard,
}: {
  submitting: boolean;
  onDiscard: () => void;
}) {
  return (
    <>
      <Button variant="ghost" onClick={onDiscard}>
        Discard
      </Button>
      <Button type="submit" variant="primary" loading={submitting}>
        Save
      </Button>
    </>
  );
}
