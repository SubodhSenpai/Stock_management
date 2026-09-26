"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button, ConfirmDialog } from "@/components/ui";
import { operationApi } from "@/lib/api";
import type { OperationConfig } from "@/lib/config/operations";
import { useAction } from "@/lib/hooks/useAction";
import type { Operation, OperationAction } from "@/types/api";

/**
 * The buttons at the top of a document.
 *
 * Which ones appear is decided entirely by `allowed_actions`, which the API derives
 * from the same transition table it enforces with. The UI therefore cannot offer an
 * action the server would refuse, and cannot hide one it would allow — there is no
 * second copy of the state machine here to drift out of step.
 */
export function ActionBar({
  operation,
  config,
  onChanged,
}: {
  operation: Operation;
  config: OperationConfig;
  onChanged: (operation: Operation) => void;
}) {
  const router = useRouter();
  const [confirmingCancel, setConfirmingCancel] = useState(false);

  const allowed = (action: OperationAction) => operation.allowed_actions.includes(action);

  const confirm = useAction(() => operationApi.confirm(operation.id), {
    successMessage: (result) =>
      result.status === "waiting"
        ? `${result.reference} is waiting on stock`
        : `${result.reference} is ready`,
    onSuccess: onChanged,
  });

  const validate = useAction(() => operationApi.validate(operation.id), {
    successMessage: (result) => `${result.reference} validated`,
    onSuccess: onChanged,
  });

  const checkAvailability = useAction(() => operationApi.checkAvailability(operation.id), {
    successMessage: (result) => `${result.reference} is ready`,
    onSuccess: onChanged,
  });

  const cancel = useAction(() => operationApi.cancel(operation.id), {
    successMessage: (result) => `${result.reference} cancelled`,
    onSuccess: (result) => {
      setConfirmingCancel(false);
      onChanged(result);
    },
  });

  const busy =
    confirm.pending || validate.pending || checkAvailability.pending || cancel.pending;

  return (
    <div className="no-print flex flex-wrap items-center gap-2">
      {allowed("confirm") && (
        <Button
          variant="primary"
          loading={confirm.pending}
          disabled={busy}
          onClick={() => void confirm.run()}
        >
          {/* Odoo calls this "Mark as Todo": it moves a draft into the work queue. */}
          To Do
        </Button>
      )}

      {allowed("validate") && (
        <Button
          variant="primary"
          loading={validate.pending}
          disabled={busy}
          onClick={() => void validate.run()}
        >
          {config.validateLabel}
        </Button>
      )}

      {allowed("check_availability") && (
        <Button
          loading={checkAvailability.pending}
          disabled={busy}
          onClick={() => void checkAvailability.run()}
        >
          Check Availability
        </Button>
      )}

      {operation.status === "done" && (
        <Button onClick={() => router.push(`/operations/${config.slug}/${operation.id}/print`)}>
          Print
        </Button>
      )}

      {allowed("cancel") && (
        <Button variant="danger" disabled={busy} onClick={() => setConfirmingCancel(true)}>
          Cancel
        </Button>
      )}

      <ConfirmDialog
        open={confirmingCancel}
        title={`Cancel ${operation.reference}?`}
        message={
          operation.status === "ready"
            ? "The stock reserved for this document will be released and made available to other documents. This cannot be undone."
            : "The document will be closed without moving any stock. This cannot be undone."
        }
        confirmLabel="Cancel document"
        destructive
        pending={cancel.pending}
        onConfirm={() => void cancel.run()}
        onClose={() => setConfirmingCancel(false)}
      />
    </div>
  );
}
