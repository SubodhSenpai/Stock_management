"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Badge, Button, DataTable, ErrorState, TableSkeleton, type Column } from "@/components/ui";
import { operationApi } from "@/lib/api";
import { cn } from "@/lib/cn";
import type { OperationConfig } from "@/lib/config/operations";
import { formatDate, formatDateTime, formatQuantity, productLabel, userLabel } from "@/lib/format";
import { useResource } from "@/lib/hooks/useResource";
import type { Operation, OperationLine } from "@/types/api";
import { ActionBar } from "./ActionBar";
import { FormSection, FormSheet, ReadField } from "./FormSheet";
import { StatusStepper } from "./StatusBadge";

/**
 * One document, read-only, with its lifecycle buttons.
 *
 * Editing is a separate screen and only offered while the document is a draft, which is
 * the same rule the server applies. Once confirmed, a document is a record of what was
 * agreed, so the fields are shown rather than exposed for change.
 */
export function OperationDetail({
  config,
  operationId,
}: {
  config: OperationConfig;
  operationId: number;
}) {
  const router = useRouter();

  const resource = useResource<Operation>(
    () => operationApi.get(operationId),
    [operationId],
    ["operation.changed", "stock.changed"],
  );

  if (resource.initialLoading) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-5">
        <div className="sheet p-6">
          <TableSkeleton rows={5} columns={3} />
        </div>
      </div>
    );
  }

  if (resource.error || !resource.data) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-5">
        <div className="sheet">
          {resource.error ? (
            <ErrorState error={resource.error} onRetry={resource.refetch} />
          ) : null}
        </div>
      </div>
    );
  }

  const operation = resource.data;
  const isCounted = config.quantityField === "counted_quantity";
  const shortLines = operation.lines.filter((line) => !line.is_available);
  const canEdit = operation.status === "draft";

  const columns: Column<OperationLine>[] = [
    {
      key: "product",
      header: "Product",
      cell: (line) => (
        <Link
          href={`/products/${line.product.id}`}
          className="text-ink hover:text-accent-600 hover:underline"
        >
          {productLabel(line.product)}
        </Link>
      ),
    },
    ...(isCounted
      ? ([
          {
            key: "system",
            header: "On Hand",
            align: "right",
            cell: (line: OperationLine) => formatQuantity(line.system_quantity),
          },
          {
            key: "counted",
            header: "Counted",
            align: "right",
            cell: (line: OperationLine) => (
              <span className="font-medium">{formatQuantity(line.counted_quantity)}</span>
            ),
          },
          {
            key: "difference",
            header: "Difference",
            align: "right",
            cell: (line: OperationLine) => {
              const difference =
                Number(line.counted_quantity ?? 0) - Number(line.system_quantity ?? 0);
              return (
                <span
                  className={cn(
                    "font-medium",
                    difference > 0 && "text-emerald-700",
                    difference < 0 && "text-rose-700",
                    difference === 0 && "text-ink-muted",
                  )}
                >
                  {difference > 0 ? "+" : ""}
                  {formatQuantity(String(difference))}
                </span>
              );
            },
          },
        ] as Column<OperationLine>[])
      : ([
          {
            key: "quantity",
            header: "Quantity",
            align: "right",
            cell: (line: OperationLine) => (
              <span className="font-medium">{formatQuantity(line.quantity)}</span>
            ),
          },
          {
            key: "available",
            header: "Available",
            align: "right",
            cell: (line: OperationLine) =>
              line.is_available ? (
                <span className="text-emerald-700">{formatQuantity(line.available_quantity)}</span>
              ) : (
                <span
                  className="font-medium text-rose-700"
                  title={`Only ${formatQuantity(line.available_quantity)} free at ${operation.source_location.code}`}
                >
                  {formatQuantity(line.available_quantity)}
                </span>
              ),
          },
        ] as Column<OperationLine>[])),
  ];

  return (
    <FormSheet
      title={operation.reference}
      status={<StatusStepper status={operation.status} statuses={config.statuses} />}
      actions={
        <>
          <ActionBar
            operation={operation}
            config={config}
            onChanged={() => {
              resource.refetch();
              router.refresh();
            }}
          />
          {canEdit && (
            <Link href={`/operations/${config.slug}/${operation.id}/edit`}>
              <Button>Edit</Button>
            </Link>
          )}
          <Link href={`/operations/${config.slug}`} className="ml-auto">
            <Button variant="ghost">Back to {config.title}</Button>
          </Link>
        </>
      }
    >
      {/* The mockup's red line warning, stated once at the top as well as per line. */}
      {operation.status === "waiting" && shortLines.length > 0 && (
        <div
          role="alert"
          className="mt-4 rounded border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900"
        >
          <p className="font-medium">
            Waiting on stock: {shortLines.length} line{shortLines.length === 1 ? "" : "s"} cannot be
            filled from {operation.source_location.code}.
          </p>
          <p className="mt-0.5 text-xs">
            This becomes Ready on its own as soon as a receipt brings the stock in, or press
            Check Availability to retry now.
          </p>
        </div>
      )}

      <FormSection>
        {operation.partner && (
          <ReadField label={config.partnerLabel ?? "Contact"}>{operation.partner.name}</ReadField>
        )}

        <ReadField label="From">{operation.source_location.code}</ReadField>
        <ReadField label="To">{operation.dest_location.code}</ReadField>

        <ReadField label="Schedule Date">
          <span className="flex items-center gap-2">
            {formatDate(operation.schedule_date)}
            {operation.is_late && (
              <Badge className="bg-rose-100 text-rose-700 ring-rose-300">Late</Badge>
            )}
          </span>
        </ReadField>

        <ReadField label="Responsible">
          {operation.responsible ? userLabel(operation.responsible) : "—"}
        </ReadField>

        {operation.validated_at && (
          <ReadField label="Validated">{formatDateTime(operation.validated_at)}</ReadField>
        )}

        {operation.delivery_address && (
          <ReadField label="Delivery Address">{operation.delivery_address}</ReadField>
        )}

        {operation.notes && <ReadField label="Notes">{operation.notes}</ReadField>}
      </FormSection>

      <section className="mt-6">
        <h2 className="border-b border-line pb-2 text-sm font-semibold uppercase tracking-wide text-brand-700">
          Products
        </h2>
        <DataTable
          columns={columns}
          rows={operation.lines}
          rowKey={(line) => line.id}
          caption={`Products on ${operation.reference}`}
          rowClassName={(line) => (!line.is_available ? "bg-rose-50/60" : undefined)}
        />
      </section>
    </FormSheet>
  );
}
