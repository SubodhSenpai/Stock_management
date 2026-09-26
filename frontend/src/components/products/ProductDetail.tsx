"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { FormSection, FormSheet, ReadField } from "@/components/operations/FormSheet";
import {
  Badge,
  Button,
  ConfirmDialog,
  DataTable,
  EmptyState,
  ErrorState,
  TableSkeleton,
  type Column,
} from "@/components/ui";
import { catalogApi } from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatMoney, formatQuantity } from "@/lib/format";
import { useAction } from "@/lib/hooks/useAction";
import { useResource } from "@/lib/hooks/useResource";
import { useSession } from "@/providers/SessionProvider";
import type { Product, ProductLocationStock } from "@/types/api";

/** One product, with where its stock actually sits. */
export function ProductDetail({ productId }: { productId: number }) {
  const router = useRouter();
  const { isManager } = useSession();
  const [confirmingArchive, setConfirmingArchive] = useState(false);

  const product = useResource<Product>(() => catalogApi.getProduct(productId), [productId]);

  const stock = useResource<ProductLocationStock[]>(
    () => catalogApi.productStock(productId),
    [productId],
    ["stock.changed"],
  );

  const archive = useAction(() => catalogApi.archiveProduct(productId), {
    successMessage: () => "Product archived",
    onSuccess: () => {
      setConfirmingArchive(false);
      product.refetch();
    },
  });

  if (product.initialLoading) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-5">
        <div className="sheet p-6">
          <TableSkeleton rows={4} columns={3} />
        </div>
      </div>
    );
  }

  if (product.error) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-5">
        <div className="sheet">
          <ErrorState error={product.error} onRetry={product.refetch} />
        </div>
      </div>
    );
  }

  const item = product.data;
  if (!item) return null;

  const rows = stock.data ?? [];
  const totals = rows.reduce(
    (sum, row) => ({
      on_hand: sum.on_hand + Number(row.on_hand),
      reserved: sum.reserved + Number(row.reserved),
      free: sum.free + Number(row.free_to_use),
    }),
    { on_hand: 0, reserved: 0, free: 0 },
  );

  const columns: Column<ProductLocationStock>[] = [
    {
      key: "location",
      header: "Location",
      cell: (row) => row.location.code,
    },
    {
      key: "on_hand",
      header: "On hand",
      align: "right",
      cell: (row) => <span className="font-medium">{formatQuantity(row.on_hand)}</span>,
    },
    {
      key: "reserved",
      header: "Reserved",
      align: "right",
      cell: (row) =>
        Number(row.reserved) > 0 ? (
          <span className="text-amber-700">{formatQuantity(row.reserved)}</span>
        ) : (
          <span className="text-ink-muted">—</span>
        ),
    },
    {
      key: "free",
      header: "Free to use",
      align: "right",
      cell: (row) => (
        <span
          className={cn(
            "font-semibold",
            Number(row.free_to_use) <= 0 ? "text-rose-600" : "text-emerald-700",
          )}
        >
          {formatQuantity(row.free_to_use)}
        </span>
      ),
    },
  ];

  return (
    <FormSheet
      title={item.name}
      subtitle={item.sku}
      status={
        item.is_active ? undefined : (
          <Badge className="bg-slate-100 text-slate-600 ring-slate-300">Archived</Badge>
        )
      }
      actions={
        <>
          {isManager && (
            <>
              <Button variant="primary" onClick={() => router.push(`/products/${item.id}/edit`)}>
                Edit
              </Button>
              {item.is_active && (
                <Button variant="danger" onClick={() => setConfirmingArchive(true)}>
                  Archive
                </Button>
              )}
            </>
          )}
          <Link href={`/moves?q=${encodeURIComponent(item.sku)}`}>
            <Button>Move history</Button>
          </Link>
          <Link href="/products" className="ml-auto">
            <Button variant="ghost">Back to Products</Button>
          </Link>
        </>
      }
    >
      <FormSection>
        <ReadField label="Category">{item.category.name}</ReadField>
        <ReadField label="Unit of measure">
          {item.uom.name} ({item.uom.code})
        </ReadField>
        <ReadField label="Per unit cost">{formatMoney(item.unit_cost)}</ReadField>
        <ReadField label="Total on hand">
          <span className="font-semibold">{formatQuantity(String(totals.on_hand))}</span>{" "}
          <span className="text-ink-muted">
            ({formatQuantity(String(totals.free))} free, {formatQuantity(String(totals.reserved))}{" "}
            reserved)
          </span>
        </ReadField>
        <ReadField label="Stock value">
          {formatMoney(String(totals.on_hand * Number(item.unit_cost)))}
        </ReadField>
      </FormSection>

      <section className="mt-6">
        <h2 className="border-b border-line pb-2 text-sm font-semibold uppercase tracking-wide text-brand-700">
          Stock by location
        </h2>

        {stock.initialLoading && <TableSkeleton rows={3} columns={4} />}
        {stock.error && <ErrorState error={stock.error} onRetry={stock.refetch} />}

        {!stock.initialLoading && !stock.error && rows.length === 0 && (
          <EmptyState
            title="No stock anywhere"
            description="Validate a receipt or record a count to bring this product into stock."
            action={
              <Link href="/operations/receipts/new">
                <Button variant="primary">New Receipt</Button>
              </Link>
            }
          />
        )}

        {rows.length > 0 && (
          <DataTable
            columns={columns}
            rows={rows}
            rowKey={(row) => row.location.id}
            caption={`Stock of ${item.name} by location`}
          />
        )}
      </section>

      <ConfirmDialog
        open={confirmingArchive}
        title={`Archive ${item.name}?`}
        message="Archived products are hidden from the catalogue and cannot be added to new documents. Past documents and the ledger are unaffected."
        confirmLabel="Archive"
        destructive
        pending={archive.pending}
        onConfirm={() => void archive.run()}
        onClose={() => setConfirmingArchive(false)}
      />
    </FormSheet>
  );
}
