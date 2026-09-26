"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Badge,
  Button,
  ControlPanel,
  DataTable,
  EmptyState,
  ErrorState,
  FilterChip,
  Pagination,
  SearchInput,
  Select,
  TableSkeleton,
  type Column,
} from "@/components/ui";
import { catalogApi } from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatMoney, formatQuantity } from "@/lib/format";
import { useResource } from "@/lib/hooks/useResource";
import { useUrlFilters } from "@/lib/hooks/useUrlFilters";
import { useSession } from "@/providers/SessionProvider";
import type { Category, Page, ProductWithStock } from "@/types/api";

const PAGE_SIZE = 20;

/** The catalogue, with each product's stock beside it. */
export function ProductList() {
  const router = useRouter();
  const filters = useUrlFilters();
  const { isManager } = useSession();

  const page = filters.getNumber("page") ?? 1;
  const query = filters.get("q") ?? "";
  const categoryId = filters.getNumber("category_id");
  const includeArchived = filters.getBoolean("include_archived");

  const categories = useResource<Category[]>(() => catalogApi.listCategories(), []);

  const products = useResource<Page<ProductWithStock>>(
    () =>
      catalogApi.listProducts({
        q: query || undefined,
        category_id: categoryId,
        include_archived: includeArchived || undefined,
        page,
        page_size: PAGE_SIZE,
      }),
    [query, categoryId, includeArchived, page],
    ["stock.changed"],
  );

  const columns: Column<ProductWithStock>[] = [
    {
      key: "sku",
      header: "SKU",
      cell: (product) => (
        <span className="font-mono text-xs text-ink-muted">{product.sku}</span>
      ),
    },
    {
      key: "name",
      header: "Product",
      cell: (product) => (
        <span className="flex items-center gap-2">
          <span className={cn("font-medium", !product.is_active && "text-ink-muted line-through")}>
            {product.name}
          </span>
          {!product.is_active && (
            <Badge className="bg-slate-100 text-slate-600 ring-slate-300">Archived</Badge>
          )}
        </span>
      ),
    },
    {
      key: "category",
      header: "Category",
      secondary: true,
      cell: (product) => <span className="text-ink-muted">{product.category.name}</span>,
    },
    {
      key: "cost",
      header: "Per unit cost",
      align: "right",
      secondary: true,
      cell: (product) => formatMoney(product.unit_cost),
    },
    {
      key: "on_hand",
      header: "On hand",
      align: "right",
      cell: (product) => (
        <span className="flex items-center justify-end gap-2">
          <span className="font-medium">{formatQuantity(product.on_hand)}</span>
          <span className="text-xs text-ink-muted">{product.uom.code}</span>
        </span>
      ),
    },
    {
      key: "free",
      header: "Free to use",
      align: "right",
      cell: (product) => (
        <span
          className={cn(
            "font-semibold",
            Number(product.free_to_use) <= 0 ? "text-rose-600" : "text-emerald-700",
          )}
        >
          {formatQuantity(product.free_to_use)}
        </span>
      ),
    },
    {
      key: "low",
      header: <span className="sr-only">Stock warning</span>,
      align: "right",
      cell: (product) =>
        product.is_low_stock ? (
          <Badge
            className="bg-amber-100 text-amber-800 ring-amber-300"
            title="At or below the minimum set by a reordering rule"
          >
            Low
          </Badge>
        ) : null,
    },
  ];

  const body = () => {
    if (products.initialLoading) return <TableSkeleton columns={columns.length} />;
    if (products.error) return <ErrorState error={products.error} onRetry={products.refetch} />;

    const items = products.data?.items ?? [];
    if (items.length === 0) {
      return (
        <EmptyState
          title={filters.active ? "No products match those filters" : "No products yet"}
          description={
            filters.active ? undefined : "Add the things you keep in stock to get started."
          }
          action={
            filters.active ? (
              <Button onClick={filters.clear}>Clear filters</Button>
            ) : isManager ? (
              <Link href="/products/new">
                <Button variant="primary">New Product</Button>
              </Link>
            ) : undefined
          }
        />
      );
    }

    return (
      <>
        <DataTable
          columns={columns}
          rows={items}
          rowKey={(product) => product.id}
          caption="Products with their stock"
          onRowClick={(product) => router.push(`/products/${product.id}`)}
        />
        <Pagination
          page={page}
          pageSize={PAGE_SIZE}
          total={products.data?.total ?? 0}
          onPageChange={(next) => filters.set({ page: next })}
        />
      </>
    );
  };

  return (
    <>
      <ControlPanel
        title="Products"
        actions={
          // Only a manager may create products; the server refuses anyone else, and
          // hiding the button keeps the user from finding that out the hard way.
          isManager ? (
            <Link href="/products/new">
              <Button variant="primary" size="sm">
                New
              </Button>
            </Link>
          ) : undefined
        }
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
              Category
              <Select
                value={categoryId ?? ""}
                placeholder="All"
                className="odoo-input w-44"
                onChange={(event) =>
                  filters.set({ category_id: event.target.value || undefined })
                }
              >
                {(categories.data ?? []).map((category) => (
                  <option key={category.id} value={category.id}>
                    {category.name}
                  </option>
                ))}
              </Select>
            </label>

            <FilterChip
              active={includeArchived}
              onClick={() => filters.set({ include_archived: !includeArchived })}
            >
              Include archived
            </FilterChip>

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
