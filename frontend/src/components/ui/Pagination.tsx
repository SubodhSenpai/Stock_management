"use client";

import { Button } from "./Button";

/**
 * Odoo's compact pager: "21-40 / 57" with a step either side.
 *
 * Used by every page-numbered list. The ledger has its own control, because it is
 * cursor-paginated and cannot know a total without counting the whole table.
 */
export function Pagination({
  page,
  pageSize,
  total,
  onPageChange,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
}) {
  if (total === 0) return null;

  const first = (page - 1) * pageSize + 1;
  const last = Math.min(page * pageSize, total);
  const lastPage = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="flex items-center justify-end gap-1 px-3 py-2 text-xs text-ink-muted">
      <span aria-live="polite">
        <span className="font-medium text-ink">
          {first}-{last}
        </span>{" "}
        / {total}
      </span>
      <Button
        variant="ghost"
        size="sm"
        aria-label="Previous page"
        disabled={page <= 1}
        onClick={() => onPageChange(page - 1)}
      >
        ‹
      </Button>
      <Button
        variant="ghost"
        size="sm"
        aria-label="Next page"
        disabled={page >= lastPage}
        onClick={() => onPageChange(page + 1)}
      >
        ›
      </Button>
    </div>
  );
}

/** The ledger's pager: there is no total, so it offers "Load more" instead of pages. */
export function CursorPagination({
  hasMore,
  loading,
  shown,
  onLoadMore,
}: {
  hasMore: boolean;
  loading: boolean;
  shown: number;
  onLoadMore: () => void;
}) {
  return (
    <div className="flex items-center justify-between gap-2 border-t border-line px-3 py-2.5 text-xs text-ink-muted">
      <span>{shown} moves shown</span>
      {hasMore ? (
        <Button size="sm" loading={loading} onClick={onLoadMore}>
          Load more
        </Button>
      ) : (
        <span>End of the ledger</span>
      )}
    </div>
  );
}
