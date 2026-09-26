"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";
import { Button, ErrorState, TableSkeleton } from "@/components/ui";
import { operationApi } from "@/lib/api";
import type { OperationConfig } from "@/lib/config/operations";
import { formatDate, formatDateTime, formatQuantity, productLabel, userLabel } from "@/lib/format";
import { useResource } from "@/lib/hooks/useResource";
import type { Operation } from "@/types/api";

/**
 * The printable slip for a validated document.
 *
 * The print dialog opens once the data has arrived, so the page is never sent to the
 * printer half-rendered. Everything not part of the document carries `no-print` and is
 * removed by the print stylesheet.
 */
export function OperationPrint({
  config,
  operationId,
}: {
  config: OperationConfig;
  operationId: number;
}) {
  const resource = useResource<Operation>(() => operationApi.get(operationId), [operationId]);
  const printed = useRef(false);
  const operation = resource.data;

  useEffect(() => {
    if (!operation || printed.current) return;
    printed.current = true;
    // A frame's delay lets the layout settle before the dialog freezes it.
    const timer = setTimeout(() => window.print(), 300);
    return () => clearTimeout(timer);
  }, [operation]);

  if (resource.initialLoading) {
    return (
      <div className="mx-auto max-w-3xl p-6">
        <TableSkeleton rows={6} columns={3} />
      </div>
    );
  }

  if (resource.error) {
    return (
      <div className="mx-auto max-w-3xl p-6">
        <ErrorState error={resource.error} onRetry={resource.refetch} />
      </div>
    );
  }

  if (!operation) return null;
  const isCounted = config.quantityField === "counted_quantity";

  return (
    <div className="mx-auto max-w-3xl px-6 py-8">
      <div className="no-print mb-4 flex items-center justify-between gap-3">
        <Link href={`/operations/${config.slug}/${operation.id}`}>
          <Button variant="ghost">Back to the document</Button>
        </Link>
        <Button variant="primary" onClick={() => window.print()}>
          Print
        </Button>
      </div>

      <article className="sheet p-8">
        <header className="flex items-start justify-between gap-6 border-b-2 border-brand-600 pb-4">
          <div>
            <p className="text-lg font-bold text-brand-700">StockSense</p>
            <p className="text-xs text-ink-muted">Inventory management</p>
          </div>
          <div className="text-right">
            <p className="text-xs uppercase tracking-wide text-ink-muted">{config.singular}</p>
            <p className="font-mono text-lg font-semibold">{operation.reference}</p>
          </div>
        </header>

        <dl className="mt-5 grid grid-cols-2 gap-x-8 gap-y-2 text-sm">
          {operation.partner && (
            <Row label={config.partnerLabel ?? "Contact"} value={operation.partner.name} />
          )}
          <Row label="From" value={operation.source_location.code} />
          <Row label="To" value={operation.dest_location.code} />
          <Row label="Schedule date" value={formatDate(operation.schedule_date)} />
          {operation.responsible && (
            <Row label="Responsible" value={userLabel(operation.responsible)} />
          )}
          {operation.validated_at && (
            <Row label="Validated" value={formatDateTime(operation.validated_at)} />
          )}
          {operation.delivery_address && (
            <Row label="Delivery address" value={operation.delivery_address} />
          )}
        </dl>

        <table className="mt-6 w-full border-collapse text-sm">
          <thead>
            <tr className="border-y border-line">
              <th scope="col" className="py-2 text-left font-semibold">
                Product
              </th>
              <th scope="col" className="w-32 py-2 text-right font-semibold">
                {isCounted ? "Counted" : "Quantity"}
              </th>
            </tr>
          </thead>
          <tbody>
            {operation.lines.map((line) => (
              <tr key={line.id} className="border-b border-line/70">
                <td className="py-2">{productLabel(line.product)}</td>
                <td className="py-2 text-right font-medium">
                  {formatQuantity(isCounted ? line.counted_quantity : line.quantity)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {operation.notes && (
          <p className="mt-5 whitespace-pre-wrap border-t border-line pt-3 text-sm text-ink-muted">
            {operation.notes}
          </p>
        )}

        <footer className="mt-10 grid grid-cols-2 gap-8 text-xs text-ink-muted">
          <div className="border-t border-line pt-2">Prepared by</div>
          <div className="border-t border-line pt-2">Received by</div>
        </footer>
      </article>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-ink-muted">{label}</dt>
      <dd className="text-ink">{value}</dd>
    </div>
  );
}
