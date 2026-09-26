"use client";

import Link from "next/link";
import {
  Button,
  ControlPanel,
  EmptyState,
  ErrorState,
  Select,
  Skeleton,
} from "@/components/ui";
import { dashboardApi } from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatQuantity, productLabel } from "@/lib/format";
import { useResource } from "@/lib/hooks/useResource";
import { useWarehouses } from "@/lib/hooks/useReferenceData";
import { useUrlFilters } from "@/lib/hooks/useUrlFilters";
import { useSession } from "@/providers/SessionProvider";
import type { DashboardSummary, LowStockItem } from "@/types/api";
import { OperationCard } from "./OperationCard";

/**
 * The landing screen: what needs doing, and what is running out.
 *
 * Every number refetches when the server reports a change, so two people working at
 * once see the same figures without either pressing reload.
 */
export function Dashboard() {
  const { user } = useSession();
  const filters = useUrlFilters();
  const warehouseId = filters.getNumber("warehouse_id");

  const warehouses = useWarehouses();

  const summary = useResource<DashboardSummary>(
    () => dashboardApi.summary({ warehouse_id: warehouseId }),
    [warehouseId],
    ["operation.changed", "stock.changed"],
  );

  const lowStock = useResource<LowStockItem[]>(
    () => dashboardApi.lowStock({ warehouse_id: warehouseId, limit: 8 }),
    [warehouseId],
    ["stock.changed"],
  );

  const firstName = (user.full_name ?? user.login_id).split(" ")[0];

  return (
    <>
      <ControlPanel
        title="Dashboard"
        subtitle={`Welcome back, ${firstName}`}
        filters={
          <label className="flex items-center gap-2 text-xs text-ink-muted">
            Warehouse
            <Select
              value={warehouseId ?? ""}
              placeholder="All warehouses"
              className="odoo-input w-48"
              onChange={(event) =>
                filters.set({ warehouse_id: event.target.value || undefined })
              }
            >
              {(warehouses.data ?? []).map((warehouse) => (
                <option key={warehouse.id} value={warehouse.id}>
                  {warehouse.name}
                </option>
              ))}
            </Select>
          </label>
        }
      />

      <div className="space-y-5 p-4">
        {summary.error ? (
          <div className="sheet">
            <ErrorState error={summary.error} onRetry={summary.refetch} />
          </div>
        ) : (
          <>
            <section aria-label="Stock overview" className="grid gap-3 sm:grid-cols-3">
              <KpiTile
                label="Products in stock"
                value={summary.data?.products_in_stock}
                loading={summary.initialLoading}
                href="/stock"
              />
              <KpiTile
                label="Out of stock"
                value={summary.data?.out_of_stock}
                loading={summary.initialLoading}
                tone={summary.data && summary.data.out_of_stock > 0 ? "danger" : "neutral"}
                href="/products"
              />
              <KpiTile
                label="Below reorder level"
                value={summary.data?.low_stock}
                loading={summary.initialLoading}
                tone={summary.data && summary.data.low_stock > 0 ? "warn" : "neutral"}
                href="/products/reorder-rules"
              />
            </section>

            <section aria-label="Operations" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {summary.initialLoading
                ? Array.from({ length: 4 }).map((_, index) => (
                    <div key={index} className="sheet p-4">
                      <Skeleton className="h-4 w-24" />
                      <Skeleton className="mt-4 h-9 w-16" />
                      <Skeleton className="mt-4 h-3 w-full" />
                    </div>
                  ))
                : summary.data?.cards.map((card) => (
                    <OperationCard key={card.type} card={card} />
                  ))}
            </section>
          </>
        )}

        <LowStockPanel resource={lowStock} />
      </div>
    </>
  );
}

function KpiTile({
  label,
  value,
  loading,
  tone = "neutral",
  href,
}: {
  label: string;
  value: number | undefined;
  loading: boolean;
  tone?: "neutral" | "warn" | "danger";
  href: string;
}) {
  return (
    <Link href={href} className="sheet block p-4 transition-shadow hover:shadow-md">
      <p className="text-xs uppercase tracking-wide text-ink-muted">{label}</p>
      {loading ? (
        <Skeleton className="mt-2 h-8 w-16" />
      ) : (
        <p
          className={cn(
            "mt-1 text-3xl font-semibold",
            tone === "danger" && "text-rose-600",
            tone === "warn" && "text-amber-600",
            tone === "neutral" && "text-ink",
          )}
        >
          {value ?? 0}
        </p>
      )}
    </Link>
  );
}

/** What is running out, straight from the reordering rules. */
function LowStockPanel({
  resource,
}: {
  resource: ReturnType<typeof useResource<LowStockItem[]>>;
}) {
  const items = resource.data ?? [];

  return (
    <section className="sheet" aria-label="Low stock">
      <header className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
        <h2 className="text-sm font-semibold text-brand-700">Needs reordering</h2>
        <Link href="/products/reorder-rules" className="text-xs text-accent-600 hover:underline">
          Reordering rules
        </Link>
      </header>

      {resource.initialLoading && (
        <div className="space-y-2 p-4">
          {Array.from({ length: 3 }).map((_, index) => (
            <Skeleton key={index} className="h-5 w-full" />
          ))}
        </div>
      )}

      {resource.error && <ErrorState error={resource.error} onRetry={resource.refetch} />}

      {!resource.initialLoading && !resource.error && items.length === 0 && (
        <EmptyState
          title="Everything is above its reorder level"
          description="Products fall into this list when their stock drops to the minimum set by a reordering rule."
          action={
            <Link href="/products/reorder-rules">
              <Button>Set a rule</Button>
            </Link>
          }
        />
      )}

      {items.length > 0 && (
        <ul className="divide-y divide-line/70">
          {items.map((item) => (
            <li
              key={`${item.product.id}-${item.warehouse_id}`}
              className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5"
            >
              <div className="min-w-0">
                <Link
                  href={`/products/${item.product.id}`}
                  className="truncate text-sm text-ink hover:text-accent-600 hover:underline"
                >
                  {productLabel(item.product)}
                </Link>
                <p className="text-xs text-ink-muted">{item.warehouse_name}</p>
              </div>

              <div className="flex items-center gap-4 text-xs">
                <span className="text-ink-muted">
                  <span
                    className={cn(
                      "font-semibold",
                      Number(item.on_hand) <= 0 ? "text-rose-600" : "text-amber-600",
                    )}
                  >
                    {formatQuantity(item.on_hand)}
                  </span>{" "}
                  / {formatQuantity(item.min_quantity)} min
                </span>
                <Link
                  href="/operations/receipts/new"
                  className="whitespace-nowrap rounded border border-line px-2 py-1 text-ink-muted transition-colors hover:border-accent-500 hover:text-accent-600"
                >
                  Order {formatQuantity(item.suggested_order)}
                </Link>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
