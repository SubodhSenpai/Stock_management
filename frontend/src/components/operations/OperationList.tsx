"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
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
  TableSkeleton,
  ViewToggle,
  type Column,
} from "@/components/ui";
import { operationApi } from "@/lib/api";
import type { OperationConfig } from "@/lib/config/operations";
import { STATUS_STYLES } from "@/lib/config/status";
import { formatDate, userLabel } from "@/lib/format";
import { useResource } from "@/lib/hooks/useResource";
import { useUrlFilters } from "@/lib/hooks/useUrlFilters";
import type { OperationStatus, OperationSummary, Page } from "@/types/api";
import { StatusBadge } from "./StatusBadge";
import { OperationKanban } from "./OperationKanban";

const PAGE_SIZE = 20;

/**
 * The list screen for one document type.
 *
 * Filters live in the URL, so a filtered view can be shared or bookmarked and survives
 * a refresh. The list refetches itself when the server reports that a document changed,
 * which is how a colleague's validation appears here without anyone pressing reload.
 */
export function OperationList({ config }: { config: OperationConfig }) {
  const router = useRouter();
  const filters = useUrlFilters();
  const [view, setView] = useState<"list" | "kanban">("list");

  const page = filters.getNumber("page") ?? 1;
  const query = filters.get("q") ?? "";
  const statuses = filters.getAll("status") as OperationStatus[];
  const late = filters.getBoolean("late");

  const operations = useResource<Page<OperationSummary>>(
    () =>
      operationApi.list({
        type: config.api,
        status: statuses.length ? statuses : undefined,
        q: query || undefined,
        late: late || undefined,
        page,
        // The kanban shows every column at once, so it needs more than one page of rows.
        page_size: view === "kanban" ? 100 : PAGE_SIZE,
      }),
    [config.api, statuses.join(","), query, late, page, view],
    ["operation.changed"],
  );

  const toggleStatus = (status: OperationStatus) => {
    const next = statuses.includes(status)
      ? statuses.filter((value) => value !== status)
      : [...statuses, status];
    filters.set({ status: next });
  };

  const columns: Column<OperationSummary>[] = [
    {
      key: "reference",
      header: "Reference",
      cell: (row) => (
        <span className="font-mono text-xs font-semibold text-brand-700">{row.reference}</span>
      ),
    },
    {
      key: "from",
      header: "From",
      secondary: true,
      cell: (row) => <span className="text-ink-muted">{row.source_location.code}</span>,
    },
    {
      key: "to",
      header: "To",
      secondary: true,
      cell: (row) => <span className="text-ink-muted">{row.dest_location.code}</span>,
    },
    {
      key: "contact",
      header: "Contact",
      cell: (row) => row.partner?.name ?? <span className="text-ink-muted">—</span>,
    },
    {
      key: "schedule",
      header: "Schedule Date",
      cell: (row) => (
        <span className="flex items-center gap-2 whitespace-nowrap">
          {formatDate(row.schedule_date)}
          {row.is_late && (
            <Badge
              className="bg-rose-100 text-rose-700 ring-rose-300"
              title="Scheduled before today and still open"
            >
              Late
            </Badge>
          )}
        </span>
      ),
    },
    {
      key: "responsible",
      header: "Responsible",
      secondary: true,
      cell: (row) =>
        row.responsible ? userLabel(row.responsible) : <span className="text-ink-muted">—</span>,
    },
    {
      key: "status",
      header: "Status",
      align: "right",
      cell: (row) => <StatusBadge status={row.status} />,
    },
  ];

  const body = () => {
    if (operations.initialLoading) return <TableSkeleton columns={columns.length} />;
    if (operations.error) {
      return <ErrorState error={operations.error} onRetry={operations.refetch} />;
    }

    const items = operations.data?.items ?? [];
    if (items.length === 0) {
      return (
        <EmptyState
          title={filters.active ? "Nothing matches those filters" : `No ${config.title.toLowerCase()} yet`}
          description={filters.active ? undefined : config.emptyHint}
          action={
            filters.active ? (
              <Button onClick={filters.clear}>Clear filters</Button>
            ) : (
              <Link href={`/operations/${config.slug}/new`}>
                <Button variant="primary">New {config.singular}</Button>
              </Link>
            )
          }
        />
      );
    }

    if (view === "kanban") return <OperationKanban operations={items} config={config} />;

    return (
      <>
        <DataTable
          columns={columns}
          rows={items}
          rowKey={(row) => row.id}
          caption={`${config.title} list`}
          onRowClick={(row) => router.push(`/operations/${config.slug}/${row.id}`)}
        />
        <Pagination
          page={page}
          pageSize={PAGE_SIZE}
          total={operations.data?.total ?? 0}
          onPageChange={(next) => filters.set({ page: next })}
        />
      </>
    );
  };

  return (
    <>
      <ControlPanel
        title={config.title}
        actions={
          <Link href={`/operations/${config.slug}/new`}>
            <Button variant="primary" size="sm">
              New
            </Button>
          </Link>
        }
        search={
          <SearchInput
            value={query}
            onChange={(value) => filters.set({ q: value })}
            placeholder="Search reference or contact"
          />
        }
        viewToggle={<ViewToggle view={view} onChange={setView} />}
        filters={
          <>
            {config.statuses.map((status) => (
              <FilterChip
                key={status}
                active={statuses.includes(status)}
                onClick={() => toggleStatus(status)}
              >
                {STATUS_STYLES[status].label}
              </FilterChip>
            ))}
            <span aria-hidden className="mx-1 h-4 w-px bg-line" />
            <FilterChip active={late} onClick={() => filters.set({ late: !late })}>
              Late
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
