"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button, Field, Input, Select, Textarea } from "@/components/ui";
import { isApiError, messageOf, operationApi, type OperationPayload } from "@/lib/api";
import type { OperationConfig } from "@/lib/config/operations";
import { todayIso } from "@/lib/format";
import { useForm } from "@/lib/hooks/useForm";
import { useInternalLocations, usePartners } from "@/lib/hooks/useReferenceData";
import { useSession } from "@/providers/SessionProvider";
import { useToast } from "@/providers/ToastProvider";
import { operationSchemaFor, type OperationFormValues } from "@/lib/validation/schemas";
import type { Operation, ProductBrief } from "@/types/api";
import { FormSheet, FormSection } from "./FormSheet";
import { LinesEditor, type LineDraft } from "./LinesEditor";

/**
 * Create or edit a document.
 *
 * One component serves all four types: which fields appear comes from the type's entry
 * in the configuration table, and the schema applies that type's rules. Editing is only
 * possible while a document is a draft, which the server enforces and the caller
 * respects by not rendering this once it has moved on.
 */
export function OperationForm({
  config,
  operation,
}: {
  config: OperationConfig;
  /** Present when editing an existing draft; absent when creating. */
  operation?: Operation;
}) {
  const router = useRouter();
  const { user } = useSession();
  const { notify } = useToast();

  const locations = useInternalLocations();
  const partners = usePartners(config.partnerType);

  // Product labels for the lines, kept beside the form values rather than inside them:
  // the payload carries ids, the screen needs names.
  const [products, setProducts] = useState<Record<number, ProductBrief>>(() =>
    Object.fromEntries((operation?.lines ?? []).map((line) => [line.product.id, line.product])),
  );

  const [formError, setFormError] = useState<string>();

  const initialLines: LineDraft[] = operation
    ? operation.lines.map((line) => ({
        product_id: line.product.id,
        quantity: String(
          (config.quantityField === "counted_quantity" ? line.counted_quantity : line.quantity) ??
            "",
        ),
      }))
    : [{ product_id: 0, quantity: config.quantityField === "counted_quantity" ? "0" : "1" }];

  const form = useForm<ReturnType<typeof operationSchemaFor>>({
    schema: operationSchemaFor(config.api),
    // Selects hold strings; the schema converts them to ids on submit.
    initialValues: {
      partner_id: operation?.partner ? String(operation.partner.id) : "",
      source_location_id: pickLocation(operation?.source_location, config, "source"),
      dest_location_id: pickLocation(operation?.dest_location, config, "destination"),
      delivery_address: operation?.delivery_address ?? "",
      schedule_date: operation?.schedule_date ?? todayIso(),
      notes: operation?.notes ?? "",
      lines: initialLines,
    } satisfies OperationFormValues,
    onSubmit: async (values, helpers) => {
      setFormError(undefined);
      const payload = toPayload(values, config);
      try {
        const saved = operation
          ? await operationApi.update(operation.id, payload)
          : await operationApi.create(payload);
        notify("success", operation ? `${saved.reference} saved` : `${saved.reference} created`);
        router.push(`/operations/${config.slug}/${saved.id}`);
        router.refresh();
      } catch (error) {
        const unplaced = isApiError(error) ? helpers.applyServerErrors(error) : [];
        setFormError(unplaced[0] ?? messageOf(error));
      }
    },
  });

  const lines = (form.values.lines ?? []) as LineDraft[];
  const sourceLocationId = Number(form.values.source_location_id) || null;

  const locationOptions = locations.data ?? [];

  return (
    <form onSubmit={form.handleSubmit} noValidate>
      <FormSheet
        title={operation ? operation.reference : `New ${config.singular}`}
        subtitle={operation ? undefined : "The reference is assigned when you save."}
        formError={formError}
        actions={
          <>
            <Button variant="ghost" onClick={() => router.back()}>
              Discard
            </Button>
            <Button type="submit" variant="primary" loading={form.submitting}>
              Save
            </Button>
          </>
        }
      >
        <FormSection>
          {config.partnerLabel && (
            <Field label={config.partnerLabel} error={form.errorFor("partner_id")}>
              {(aria) => (
                <Select
                  {...aria}
                  {...form.field("partner_id")}
                  placeholder={partners.loading ? "Loading..." : "Select a contact"}
                >
                  {(partners.data ?? []).map((partner) => (
                    <option key={partner.id} value={partner.id}>
                      {partner.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          )}

          {config.locations.source && (
            <Field label={config.locations.source} error={form.errorFor("source_location_id")} required>
              {(aria) => (
                <Select
                  {...aria}
                  {...form.field("source_location_id")}
                  placeholder={locations.loading ? "Loading..." : "Select a location"}
                >
                  {locationOptions.map((location) => (
                    <option key={location.id} value={location.id}>
                      {location.code}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          )}

          {config.locations.destination && (
            <Field
              label={config.locations.destination}
              error={form.errorFor("dest_location_id")}
              required
            >
              {(aria) => (
                <Select
                  {...aria}
                  {...form.field("dest_location_id")}
                  placeholder={locations.loading ? "Loading..." : "Select a location"}
                >
                  {locationOptions.map((location) => (
                    <option key={location.id} value={location.id}>
                      {location.code}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          )}

          <Field label="Schedule Date" error={form.errorFor("schedule_date")} required>
            {(aria) => <Input {...aria} {...form.field("schedule_date")} type="date" />}
          </Field>

          <Field label="Responsible">
            {(aria) => (
              // Filled from the session and not editable here, matching the mockup's
              // "auto fill with the current logged in user".
              <Input
                {...aria}
                value={user.full_name ?? user.login_id}
                readOnly
                disabled
                className="odoo-input"
              />
            )}
          </Field>

          {config.api === "delivery" && (
            <Field
              label="Delivery Address"
              error={form.errorFor("delivery_address")}
              className="sm:col-span-2"
            >
              {(aria) => <Textarea {...aria} {...form.field("delivery_address")} rows={2} />}
            </Field>
          )}

          <Field label="Notes" error={form.errorFor("notes")} className="sm:col-span-2">
            {(aria) => <Textarea {...aria} {...form.field("notes")} rows={2} />}
          </Field>
        </FormSection>

        <LinesEditor
          lines={lines}
          products={products}
          config={config}
          sourceLocationId={sourceLocationId}
          errors={form.errors}
          onChange={(nextLines, nextProducts) => {
            form.setValue("lines", nextLines);
            setProducts(nextProducts);
          }}
        />
      </FormSheet>
    </form>
  );
}

/**
 * Only the real side of a document is editable.
 *
 * The other side is a virtual location (Vendors, Customers, Inventory Adjustment) that
 * the server fills in, so it is never pre-loaded into a select the user can change.
 */
function pickLocation(
  location: { id: number; type: string } | undefined,
  config: OperationConfig,
  side: "source" | "destination",
): string {
  const editable = side === "source" ? config.locations.source : config.locations.destination;
  if (!editable || !location || location.type !== "internal") return "";
  return String(location.id);
}

/** Form values to the request body, sending only the fields this type uses. */
function toPayload(
  values: ReturnType<ReturnType<typeof operationSchemaFor>["parse"]>,
  config: OperationConfig,
): OperationPayload {
  const counted = config.quantityField === "counted_quantity";

  return {
    type: config.api,
    ...(config.locations.source && values.source_location_id
      ? { source_location_id: values.source_location_id }
      : {}),
    ...(config.locations.destination && values.dest_location_id
      ? { dest_location_id: values.dest_location_id }
      : {}),
    ...(config.partnerLabel ? { partner_id: values.partner_id } : {}),
    ...(config.api === "delivery" ? { delivery_address: values.delivery_address } : {}),
    schedule_date: values.schedule_date,
    notes: values.notes,
    lines: values.lines.map((line) =>
      counted
        ? { product_id: line.product_id, counted_quantity: line.quantity }
        : { product_id: line.product_id, quantity: line.quantity },
    ),
  };
}
