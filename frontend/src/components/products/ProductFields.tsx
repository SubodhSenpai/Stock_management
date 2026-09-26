"use client";

import { Field, Input, Select } from "@/components/ui";
import { FormSection } from "@/components/operations/FormSheet";
import { catalogApi } from "@/lib/api";
import { useResource } from "@/lib/hooks/useResource";
import type { FieldProps } from "@/lib/hooks/useForm";
import type { Category, Uom } from "@/types/api";

/**
 * The fields a product has, whether it is being created or edited.
 *
 * The two forms differ in what they submit, not in what they show, so the inputs live
 * here and each form passes its own controller in. The binding names only the fields
 * this component touches, so a controller with extra fields — the create form has an
 * opening-stock pair — still satisfies it.
 */
export type ProductFieldName = "sku" | "name" | "category_id" | "uom_id" | "unit_cost";

export interface ProductFieldBinding {
  field: (name: ProductFieldName) => FieldProps;
  errorFor: (name: string) => string | undefined;
}

export function ProductFields({
  form,
  /**
   * True when editing. The SKU is shown but disabled rather than hidden, so it is
   * clear that it exists and why it cannot be changed: past documents already cite it.
   */
  skuLocked = false,
}: {
  form: ProductFieldBinding;
  skuLocked?: boolean;
}) {
  const categories = useResource<Category[]>(() => catalogApi.listCategories(), []);
  const uoms = useResource<Uom[]>(() => catalogApi.listUoms(), []);

  return (
    <FormSection>
      <Field
        label="SKU"
        error={form.errorFor("sku")}
        hint={
          skuLocked
            ? "Fixed once the product exists: past documents refer to it"
            : "Letters, numbers and hyphens; stored upper-case"
        }
        required
      >
        {(aria) => (
          <Input
            {...aria}
            {...form.field("sku")}
            disabled={skuLocked}
            autoFocus={!skuLocked}
          />
        )}
      </Field>

      <Field label="Name" error={form.errorFor("name")} required>
        {(aria) => <Input {...aria} {...form.field("name")} autoFocus={skuLocked} />}
      </Field>

      <Field label="Category" error={form.errorFor("category_id")} required>
        {(aria) => (
          <Select
            {...aria}
            {...form.field("category_id")}
            placeholder={categories.loading ? "Loading..." : "Select a category"}
          >
            {(categories.data ?? []).map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </Select>
        )}
      </Field>

      <Field
        label="Unit of measure"
        error={form.errorFor("uom_id")}
        hint="Units cannot be split; weights can"
        required
      >
        {(aria) => (
          <Select
            {...aria}
            {...form.field("uom_id")}
            placeholder={uoms.loading ? "Loading..." : "Select a unit"}
          >
            {(uoms.data ?? []).map((uom) => (
              <option key={uom.id} value={uom.id}>
                {uom.name} ({uom.code})
              </option>
            ))}
          </Select>
        )}
      </Field>

      <Field label="Per unit cost" error={form.errorFor("unit_cost")} required>
        {(aria) => <Input {...aria} {...form.field("unit_cost")} inputMode="decimal" />}
      </Field>
    </FormSection>
  );
}
