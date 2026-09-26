"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  Button,
  ControlPanel,
  CursorPagination,
  DataTable,
  EmptyState,
  ErrorState,
  Input,
  Select,
  TableSkeleton,
  SearchInput,
  type Column,
} from "@/components/ui";
import { isApiError, stockApi, type ApiError, type MoveFilters } from "@/lib/api";
import { cn } from "@/lib/cn";
import { DIRECTION_STYLES } from "@/lib/config/status";
import { operationHref } from "@/lib/config/operations";
import { formatDateTime, formatQuantity } from "@/lib/format";
import { useDebouncedValue } from "@/lib/hooks/useDebouncedValue";
import { useRealtime } from "@/providers/RealtimeProvider";
import { useInternalLocations, useWarehouses } from "@/lib/hooks/useReferenceData";
import { useUrlFilters } from "@/lib/hooks/useUrlFilters";
import type { OperationType, StockMove } from "@/types/api";

const PAGE_SIZE = 25;

/**
 * The stock ledger.
 *
 * Paged by cursor rather than by page number: the ledger only ever grows, so an OFFSET
 * would get slower with every page. "Load more" appends, so a page the user has already
 * scrolled through is not thrown away when the next one arrives.
 */
export function MoveHistory() {
  const filters = useUrlFilters();
  const [moves, setMoves] = useState<StockMove[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<ApiError>();

  const warehouses = useWarehouses();
  const locations = useInternalLocations();

  const query = filters.get("q") ?? "";
  const warehouseId = filters.getNumber("warehouse_id");
  const locationId = filters.getNumber("location_id");
  const dateFrom = filters.get("date_from") ?? "";
  const dateTo = filters.get("date_to") ?? "";

  // The date inputs write straight to the URL, so a partially typed year does not fire
  // a request on every keystroke.
  const settledFrom = useDebouncedValue(dateFrom, 400);
  const settledTo = useDebouncedValue(dateTo, 400);

  const load = useCallback(
    async (from?: string | null) => {
      const request: MoveFilters = {
        q: query || undefined,
        warehouse_id: warehouseId,
        location_id: locationId,
        // The API takes datetimes; a date box gives a day, so widen it to the whole day.
        date_from: settledFrom ? `${settledFrom}T00:00:00` : undefined,
        date_to: settledTo ? `${settledTo}T23:59:59` : undefined,
        cursor: from ?? undefined,
        limit: PAGE_SIZE,
      };

      if (from) setLoadingMore(true);
      else setLoading(true);

      try {
        const page = await stockApi.moves(request);
        setMoves((current) => (from ? [...current, ...page.items] : page.items));
        setCursor(page.next_cursor);
        setError(undefined);
      } catch (caught) {
        if (isApiError(caught)) setError(caught);
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }
    },
    [query, warehouseId, locationId, settledFrom, settledTo],
  );

  // Any filter change starts the ledger again from the newest entry.
  useEffect(() => {
    void load(null);
  }, [load]);

  useRealtime(["stock.changed"], () => void load(null));

  const columns: Column<StockMove>[] = [
    {
      key: "reference",
      header: "Reference",
      cell: (move) => (
        <Link
          href={operationHref(referenceType(move.reference), move.operation_id)}
          className="font-mono text-xs font-semibold text-brand-700 hover:underline"
        >
          {move.reference}
        </Link>
      ),
    },
    {
      key: "date",
      header: "Date",
      cell: (move) => <span className="whitespace-nowrap">{formatDateTime(move.moved_at)}</span>,
    },
    {
      key: "product",
      header: "Product",
      cell: (move) => (
        <Link
          href={`/products/${move.product.id}`}
          className="hover:text-accent-600 hover:underline"
        >
          {move.product.name}
          <span className="ml-2 font-mono text-xs text-ink-muted">{move.product.sku}</span>
        </Link>
      ),
    },
    {
      key: "contact",
      header: "Contact",
      secondary: true,
      cell: (move) => move.contact ?? <span className="text-ink-muted">—</span>,
    },
    {
      key: "from",
      header: "From",
      secondary: true,
      cell: (move) => <span className="text-ink-muted">{move.from_location.code}</span>,
    },
    {
      key: "to",
      header: "To",
      secondary: true,
      cell: (move) => <span className="text-ink-muted">{move.to_location.code}</span>,
    },
    {
      key: "quantity",
      header: "Quantity",
      align: "right",
      cell: (move) => {
        const style = DIRECTION_STYLES[move.direction];
        return (
          <span className={cn("font-semibold", style.className)} title={`${style.label} move`}>
            {move.direction === "in" ? "+" : move.direction === "out" ? "−" : ""}
            {formatQuantity(move.quantity)}
          </span>
        );
      },
    },
  ];

  const body = () => {
    if (loading) return <TableSkeleton columns={columns.length} />;
    if (error) return <ErrorState error={error} onRetry={() => void load(null)} />;

    if (moves.length === 0) {
      return (
        <EmptyState
          title={filters.active ? "No moves match those filters" : "The ledger is empty"}
          description={
            filters.active
              ? undefined
              : "A move is written whenever a document is validated. Nothing has been validated yet."
          }
          action={
            filters.active ? <Button onClick={filters.clear}>Clear filters</Button> : undefined
          }
        />
      );
    }

    return (
      <>
        <DataTable
          columns={columns}
          rows={moves}
          rowKey={(move) => move.id}
          caption="Stock ledger, newest first"
        />
        <CursorPagination
          hasMore={cursor !== null}
          loading={loadingMore}
          shown={moves.length}
          onLoadMore={() => void load(cursor)}
        />
      </>
    );
  };

  return (
    <>
      <ControlPanel
        title="Move History"
        subtitle="Every stock movement, newest first. This record cannot be edited."
        search={
          <SearchInput
            value={query}
            onChange={(value) => filters.set({ q: value })}
            placeholder="Search a document reference"
          />
        }
        filters={
          <>
            <label className="flex items-center gap-2 text-xs text-ink-muted">
              Warehouse
              <Select
                value={warehouseId ?? ""}
                placeholder="All"
                className="odoo-input w-40"
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
                className="odoo-input w-40"
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

            <label className="flex items-center gap-2 text-xs text-ink-muted">
              From
              <Input
                type="date"
                value={dateFrom}
                className="odoo-input w-36"
                onChange={(event) => filters.set({ date_from: event.target.value || undefined })}
              />
            </label>

            <label className="flex items-center gap-2 text-xs text-ink-muted">
              To
              <Input
                type="date"
                value={dateTo}
                className="odoo-input w-36"
                onChange={(event) => filters.set({ date_to: event.target.value || undefined })}
              />
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
    </>
  );
}

/**
 * The document type behind a reference such as `WH/OUT/0003`.
 *
 * A ledger row carries the reference and the document id but not its type, and the
 * prefixes are assigned by the backend from a fixed table (IN, OUT, INT, ADJ). This is
 * only used to build the link, so an unrecognised prefix falls back rather than
 * breaking the row.
 */
function referenceType(reference: string): OperationType {
  switch (reference.split("/")[1]?.toUpperCase()) {
    case "OUT":
      return "delivery";
    case "INT":
      return "internal";
    case "ADJ":
      return "adjustment";
    default:
      return "receipt";
  }
}
