"use client";

import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

/**
 * The list view.
 *
 * Columns are described once and rendered generically, so every table in the app lines
 * up the same way, numbers are right-aligned without each page remembering to do it,
 * and a row can be made clickable without wrapping cells in links.
 */

export interface Column<T> {
  key: string;
  header: ReactNode;
  /** Numbers read better right-aligned; everything else stays left. */
  align?: "left" | "right" | "center";
  /** Hidden below `md`, for columns that are useful but not essential on a phone. */
  secondary?: boolean;
  width?: string;
  cell: (row: T) => ReactNode;
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  onRowClick,
  rowClassName,
  caption,
  footer,
}: {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string | number;
  onRowClick?: (row: T) => void;
  rowClassName?: (row: T) => string | undefined;
  /** Describes the table for screen readers; not shown. */
  caption?: string;
  footer?: ReactNode;
}) {
  const alignment = (align: Column<T>["align"]) =>
    align === "right" ? "text-right" : align === "center" ? "text-center" : "text-left";

  return (
    <div className="scrollbar-slim overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead>
          <tr className="border-b border-line bg-canvas/60">
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                style={column.width ? { width: column.width } : undefined}
                className={cn(
                  "px-3 py-2.5 text-xs uppercase tracking-wide text-ink-muted whitespace-nowrap",
                  alignment(column.align),
                  column.secondary && "hidden md:table-cell",
                )}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>

        <tbody>
          {rows.map((row) => (
            <tr
              key={rowKey(row)}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              // A clickable row is reachable by keyboard too, not just by mouse.
              tabIndex={onRowClick ? 0 : undefined}
              role={onRowClick ? "button" : undefined}
              onKeyDown={
                onRowClick
                  ? (event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        onRowClick(row);
                      }
                    }
                  : undefined
              }
              className={cn(
                "border-b border-line/70 transition-colors last:border-0",
                onRowClick && "cursor-pointer hover:bg-brand-50/60 focus:bg-brand-50",
                rowClassName?.(row),
              )}
            >
              {columns.map((column) => (
                <td
                  key={column.key}
                  className={cn(
                    "px-3 py-2.5 align-middle",
                    alignment(column.align),
                    column.secondary && "hidden md:table-cell",
                  )}
                >
                  {column.cell(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>

        {footer && <tfoot className="border-t border-line bg-canvas/60">{footer}</tfoot>}
      </table>
    </div>
  );
}
