"use client";

import { useState } from "react";
import { FormAlert } from "@/components/auth/FormAlert";
import {
  Badge,
  Button,
  ConfirmDialog,
  ControlPanel,
  DataTable,
  EmptyState,
  ErrorState,
  Field,
  FilterChip,
  Input,
  Modal,
  TableSkeleton,
  Textarea,
  type Column,
} from "@/components/ui";
import { isApiError, messageOf, warehouseApi } from "@/lib/api";
import { useAction } from "@/lib/hooks/useAction";
import { useForm } from "@/lib/hooks/useForm";
import { useResource } from "@/lib/hooks/useResource";
import { useSession } from "@/providers/SessionProvider";
import { useToast } from "@/providers/ToastProvider";
import { warehouseEditSchema, warehouseSchema } from "@/lib/validation/schemas";
import type { Warehouse } from "@/types/api";

/**
 * Warehouses.
 *
 * The short code is part of every document reference this warehouse produces
 * (`WH/IN/0001`), so it is set once at creation and fixed thereafter.
 */
export function WarehouseManager() {
  const { isManager } = useSession();
  const [editing, setEditing] = useState<Warehouse | null>(null);
  const [creating, setCreating] = useState(false);
  const [archiving, setArchiving] = useState<Warehouse | null>(null);
  const [includeArchived, setIncludeArchived] = useState(false);

  const warehouses = useResource<Warehouse[]>(
    () => warehouseApi.list(includeArchived),
    [includeArchived],
  );

  const archive = useAction((id: number) => warehouseApi.archive(id), {
    successMessage: () => "Warehouse archived",
    onSuccess: () => {
      setArchiving(null);
      warehouses.refetch();
    },
  });

  const columns: Column<Warehouse>[] = [
    {
      key: "code",
      header: "Short code",
      cell: (warehouse) => (
        <span className="font-mono text-xs font-semibold text-brand-700">
          {warehouse.short_code}
        </span>
      ),
    },
    {
      key: "name",
      header: "Name",
      cell: (warehouse) => (
        <span className="flex items-center gap-2">
          {warehouse.name}
          {!warehouse.is_active && (
            <Badge className="bg-slate-100 text-slate-600 ring-slate-300">Archived</Badge>
          )}
        </span>
      ),
    },
    {
      key: "address",
      header: "Address",
      secondary: true,
      cell: (warehouse) => warehouse.address ?? <span className="text-ink-muted">—</span>,
    },
    ...(isManager
      ? ([
          {
            key: "actions",
            header: <span className="sr-only">Actions</span>,
            align: "right",
            cell: (warehouse: Warehouse) => (
              <span className="flex justify-end gap-1">
                <Button variant="ghost" size="sm" onClick={() => setEditing(warehouse)}>
                  Edit
                </Button>
                {warehouse.is_active && (
                  <Button variant="ghost" size="sm" onClick={() => setArchiving(warehouse)}>
                    Archive
                  </Button>
                )}
              </span>
            ),
          },
        ] as Column<Warehouse>[])
      : []),
  ];

  const body = () => {
    if (warehouses.initialLoading) return <TableSkeleton rows={3} columns={4} />;
    if (warehouses.error) {
      return <ErrorState error={warehouses.error} onRetry={warehouses.refetch} />;
    }

    const items = warehouses.data ?? [];
    if (items.length === 0) {
      return (
        <EmptyState
          title="No warehouses yet"
          description="A warehouse holds the locations that stock actually sits in."
          action={
            isManager ? (
              <Button variant="primary" onClick={() => setCreating(true)}>
                New Warehouse
              </Button>
            ) : undefined
          }
        />
      );
    }

    return (
      <DataTable
        columns={columns}
        rows={items}
        rowKey={(warehouse) => warehouse.id}
        caption="Warehouses"
      />
    );
  };

  return (
    <>
      <ControlPanel
        title="Warehouses"
        actions={
          isManager ? (
            <Button variant="primary" size="sm" onClick={() => setCreating(true)}>
              New
            </Button>
          ) : undefined
        }
        filters={
          <FilterChip active={includeArchived} onClick={() => setIncludeArchived((v) => !v)}>
            Include archived
          </FilterChip>
        }
      />

      <div className="p-4">
        <div className="sheet overflow-hidden">{body()}</div>
      </div>

      {creating && (
        <WarehouseDialog
          onClose={() => setCreating(false)}
          onSaved={() => {
            setCreating(false);
            warehouses.refetch();
          }}
        />
      )}

      {editing && (
        <WarehouseDialog
          key={editing.id}
          warehouse={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            warehouses.refetch();
          }}
        />
      )}

      <ConfirmDialog
        open={archiving !== null}
        title={`Archive ${archiving?.name ?? ""}?`}
        message="Archived warehouses are hidden from new documents. Past documents and the ledger are unaffected."
        confirmLabel="Archive"
        destructive
        pending={archive.pending}
        onConfirm={() => archiving && void archive.run(archiving.id)}
        onClose={() => setArchiving(null)}
      />
    </>
  );
}

/** Create or edit. Editing cannot touch the short code, so it uses its own schema. */
function WarehouseDialog({
  warehouse,
  onClose,
  onSaved,
}: {
  warehouse?: Warehouse;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { notify } = useToast();
  const [formError, setFormError] = useState<string>();

  const createForm = useForm({
    schema: warehouseSchema,
    initialValues: { name: "", short_code: "", address: "" },
    onSubmit: async (values, helpers) => {
      setFormError(undefined);
      try {
        const saved = await warehouseApi.create(values);
        notify("success", `${saved.name} created`);
        onSaved();
      } catch (error) {
        const unplaced = isApiError(error) ? helpers.applyServerErrors(error) : [];
        setFormError(unplaced[0] ?? messageOf(error));
      }
    },
  });

  const editForm = useForm({
    schema: warehouseEditSchema,
    initialValues: { name: warehouse?.name ?? "", address: warehouse?.address ?? "" },
    onSubmit: async (values, helpers) => {
      if (!warehouse) return;
      setFormError(undefined);
      try {
        const saved = await warehouseApi.update(warehouse.id, values);
        notify("success", `${saved.name} saved`);
        onSaved();
      } catch (error) {
        const unplaced = isApiError(error) ? helpers.applyServerErrors(error) : [];
        setFormError(unplaced[0] ?? messageOf(error));
      }
    },
  });

  const form = warehouse ? editForm : createForm;

  return (
    <Modal
      open
      title={warehouse ? `Edit ${warehouse.name}` : "New warehouse"}
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose} disabled={form.submitting}>
            Cancel
          </Button>
          <Button variant="primary" loading={form.submitting} onClick={form.handleSubmit}>
            Save
          </Button>
        </>
      }
    >
      <form onSubmit={form.handleSubmit} noValidate className="space-y-4">
        <FormAlert message={formError} />

        <Field label="Name" error={form.errorFor("name")} required>
          {(aria) =>
            warehouse ? (
              <Input {...aria} {...editForm.field("name")} autoFocus />
            ) : (
              <Input {...aria} {...createForm.field("name")} autoFocus />
            )
          }
        </Field>

        {warehouse ? (
          <Field label="Short code" hint="Fixed: it appears in every document reference">
            {(aria) => <Input {...aria} value={warehouse.short_code} disabled readOnly />}
          </Field>
        ) : (
          <Field
            label="Short code"
            error={createForm.errorFor("short_code")}
            hint="Up to 5 characters, used in references such as WH/IN/0001"
            required
          >
            {(aria) => <Input {...aria} {...createForm.field("short_code")} />}
          </Field>
        )}

        <Field label="Address" error={form.errorFor("address")}>
          {(aria) =>
            warehouse ? (
              <Textarea {...aria} {...editForm.field("address")} rows={2} />
            ) : (
              <Textarea {...aria} {...createForm.field("address")} rows={2} />
            )
          }
        </Field>

        <button type="submit" className="hidden" aria-hidden tabIndex={-1} />
      </form>
    </Modal>
  );
}
