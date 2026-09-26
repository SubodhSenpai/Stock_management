"use client";

import Link from "next/link";
import { Button, ErrorState, TableSkeleton } from "@/components/ui";
import { operationApi } from "@/lib/api";
import type { OperationConfig } from "@/lib/config/operations";
import { useResource } from "@/lib/hooks/useResource";
import type { Operation } from "@/types/api";
import { OperationForm } from "./OperationForm";

/**
 * Editing an existing document.
 *
 * Only a draft may be changed. The server refuses anything else, and this checks the
 * status it loaded so the user is told why rather than being shown a form whose save
 * would be rejected.
 */
export function OperationEditor({
  config,
  operationId,
}: {
  config: OperationConfig;
  operationId: number;
}) {
  const resource = useResource<Operation>(() => operationApi.get(operationId), [operationId]);

  if (resource.initialLoading) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-5">
        <div className="sheet p-6">
          <TableSkeleton rows={4} columns={2} />
        </div>
      </div>
    );
  }

  if (resource.error) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-5">
        <div className="sheet">
          <ErrorState error={resource.error} onRetry={resource.refetch} />
        </div>
      </div>
    );
  }

  const operation = resource.data;
  if (!operation) return null;

  if (operation.status !== "draft") {
    return (
      <div className="mx-auto max-w-5xl px-4 py-5">
        <div className="sheet flex flex-col items-center gap-3 px-6 py-14 text-center">
          <h1 className="text-base font-semibold text-ink">
            {operation.reference} can no longer be edited
          </h1>
          <p className="max-w-md text-sm text-ink-muted">
            A document is only editable while it is a draft. Once confirmed it has reserved
            stock and become a record of what was agreed.
          </p>
          <Link href={`/operations/${config.slug}/${operation.id}`}>
            <Button variant="primary">View the document</Button>
          </Link>
        </div>
      </div>
    );
  }

  return <OperationForm config={config} operation={operation} />;
}
