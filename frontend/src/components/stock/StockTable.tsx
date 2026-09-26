"use client";

import Link from "next/link";
import { useState } from "react";
import {
  Button,
  ControlPanel,
  DataTable,
  EmptyState,
  ErrorState,
  Pagination,
  SearchInput,
  Select,
  TableSkeleton,
  type Column,
} from "@/components/ui";
import { stockApi } from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatMoney, formatQuantity } from "@/lib/format";
import { useResource } from "@/lib/hooks/useResource";
import { useInternalLocations, useWarehouses } from "@/lib/hooks/useReferenceData";
import { useUrlFilters } from "@/lib/hooks/useUrlFilters";
import type { Page, StockRow } from "@/types/api";
import { AdjustStockDialog } from "./AdjustStockDialog";

const PAGE_SIZE = 20;

/**
 * Stock on hand, per product per location.
 *
 * The mockup asks that stock be updatable from this screen. It is, but not by editing a
 * number in place: "Update" opens a count, and the server turns that count into an
 * adjustment document. Every change to stock therefore leaves a ledger entry explaining
 * it, including corrections.
 */
export function StockTable() {
  const filters = useUrlFilters();
  const [adjusting, setAdjusting] = useState<StockRow | null>(null);

  const page = filters.getNumber("page") ?? 1;
  const query = filters.get("q") ?? "";
  const warehouseId = filters.getNumber("warehouse_id");
  const locationId = filters.getNumber("location_id");

  const warehouses = useWarehouses();
  const locations = useInternalLocations();

  const stock = useResource<Page<StockRow>>(
    () =>
      stockApi.list({
        q: query || undefined,
        warehouse_id: warehouseId,
        location_id: locationId,
        page,
        page_size: PAGE_SIZE,
      }),
    [query, warehouseId, locationId, page],
    ["stock.changed"],
  );

  const columns: Column<StockRow>[] = [
    {
      key: "product",
      header: "Product",
      cell: (row) => (
        <Link
          href={`/products/${row.product.id}`}
          className="text-ink hover:text-accent-600 hover:underline"
        >
          <span className="font-medium">{row.product.name}</span>
          <span className="ml-2 font-mono text-xs text-ink-muted">{row.product.sku}</span>
        </Link>
      ),
    },
    {
      key: "location",
      header: "Location",
      cell: (row) => <span className="text-ink-muted">{row.location.code}</span>,
    },
    {
      key: "cost",
      header: "Per unit cost",
      align: "right",
      secondary: true,
      cell: (row) => formatMoney(row.unit_cost),
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
      secondary: true,
      cell: (row) =>
        Number(row.reserved) > 0 ? (
          <span className="text-amber-700" title="Set aside for a confirmed document">
            {formatQuantity(row.reserved)}
          </span>
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
          title="On hand minus what is reserved"
        >
          {formatQuantity(row.free_to_use)}
        </span>
      ),
    },
    {
      key: "actions",
      header: <span className="sr-only">Actions</span>,
      align: "right",
      cell: (row) => (
        <Button size="sm" onClick={() => setAdjusting(row)}>
          Update
        </Button>
      ),
    },
  ];

  const body = () => {
    if (stock.initialLoading) return <TableSkeleton columns={columns.length} />;
    if (stock.error) return <ErrorState error={stock.error} onRetry={stock.refetch} />;

    const items = stock.data?.items ?? [];
    if (items.length === 0) {
      return (
        <EmptyState
          title={filters.active ? "Nothing matches those filters" : "No stock recorded yet"}
          description={
            filters.active
              ? undefined
              : "Stock appears here once a receipt or an adjustment has been validated."
          }
          action={
            filters.active ? (
              <Button onClick={filters.clear}>Clear filters</Button>
            ) : (
              <Link href="/operations/receipts/new">
                <Button variant="primary">New Receipt</Button>
              </Link>
            )
          }
        />
      );
    }

    return (
      <>
        <DataTable
          columns={columns}
          rows={items}
          rowKey={(row) => `${row.product.id}-${row.location.id}`}
          caption="Stock on hand by product and location"
        />
        <Pagination
          page={page}
          pageSize={PAGE_SIZE}
          total={stock.data?.total ?? 0}
          onPageChange={(next) => filters.set({ page: next })}
        />
      </>
    );
  };

  return (
    <>
      <ControlPanel
        title="Stock"
        subtitle="Free to use is on hand minus what is already reserved"
        search={
          <SearchInput
            value={query}
            onChange={(value) => filters.set({ q: value })}
            placeholder="Search name or SKU"
          />
        }
        filters={
          <>
            <label className="flex items-center gap-2 text-xs text-ink-muted">
              Warehouse
              <Select
                value={warehouseId ?? ""}
                placeholder="All"
                className="odoo-input w-44"
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

            <label className="flex items-center gap-2 text-xs text-ink-muted">
              Location
              <Select
                value={locationId ?? ""}
                placeholder="All"
                className="odoo-input w-44"
                onChange={(event) =>
                  filters.set({ location_id: event.target.value || undefined })
                }
              >
                {(locations.data ?? []).map((location) => (
                  <option key={location.id} value={location.id}>
                    {location.code}
                  </option>
                ))}
              </Select>
            </label>

            {filters.active && (
              <Button variant="link" className="ml-auto text-xs" onClick={filters.clear}>
                Clear filters
              </Button>
            )}
          </>
        }
      />

      <div className="p-4">
        <div className="sheet overflow-hidden">{body()}</div>
      </div>

      {adjusting && (
        <AdjustStockDialog
          // Keyed so choosing another row starts a fresh form rather than reusing the
          // previous product's counted quantity.
          key={`${adjusting.product.id}-${adjusting.location.id}`}
          row={adjusting}
          onClose={() => setAdjusting(null)}
          onAdjusted={() => {
            setAdjusting(null);
            stock.refetch();
          }}
        />
      )}
    </>
  );
}
