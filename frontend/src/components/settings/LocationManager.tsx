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
  Input,
  Modal,
  Select,
  TableSkeleton,
  type Column,
} from "@/components/ui";
import { isApiError, locationApi, messageOf } from "@/lib/api";
import { useAction } from "@/lib/hooks/useAction";
import { useForm } from "@/lib/hooks/useForm";
import { useResource } from "@/lib/hooks/useResource";
import { useWarehouses } from "@/lib/hooks/useReferenceData";
import { useSession } from "@/providers/SessionProvider";
import { useToast } from "@/providers/ToastProvider";
import { locationSchema } from "@/lib/validation/schemas";
import type { Location } from "@/types/api";

/**
 * The places inside a warehouse that hold stock.
 *
 * Only internal locations are listed. Vendors, Customers and Inventory Adjustment are
 * also locations in the model — that is what makes every document one kind of move —
 * but they are the system's, not something a user creates or edits.
 */
export function LocationManager() {
  const { isManager } = useSession();
  const [creating, setCreating] = useState(false);
  const [archiving, setArchiving] = useState<Location | null>(null);
  const [warehouseFilter, setWarehouseFilter] = useState<string>("");

  const warehouses = useWarehouses();
  const locations = useResource<Location[]>(
    () =>
      locationApi.list({
        type: "internal",
        warehouse_id: warehouseFilter ? Number(warehouseFilter) : undefined,
      }),
    [warehouseFilter],
  );

  const warehouseNames = new Map((warehouses.data ?? []).map((w) => [w.id, w.name]));

  const archive = useAction((id: number) => locationApi.archive(id), {
    successMessage: () => "Location archived",
    onSuccess: () => {
      setArchiving(null);
      locations.refetch();
    },
  });

  const columns: Column<Location>[] = [
    {
      key: "code",
      header: "Location",
      cell: (location) => (
        <span className="flex items-center gap-2">
          <span className="font-mono text-xs font-semibold text-brand-700">{location.code}</span>
          {!location.is_active && (
            <Badge className="bg-slate-100 text-slate-600 ring-slate-300">Archived</Badge>
          )}
        </span>
      ),
    },
    { key: "name", header: "Name", cell: (location) => location.name },
    {
      key: "warehouse",
      header: "Warehouse",
      secondary: true,
      cell: (location) =>
        location.warehouse_id ? (
          (warehouseNames.get(location.warehouse_id) ?? `#${location.warehouse_id}`)
        ) : (
          <span className="text-ink-muted">—</span>
        ),
    },
    ...(isManager
      ? ([
          {
            key: "actions",
            header: <span className="sr-only">Actions</span>,
            align: "right",
            cell: (location: Location) =>
              location.is_active ? (
                <Button variant="ghost" size="sm" onClick={() => setArchiving(location)}>
                  Archive
                </Button>
              ) : null,
          },
        ] as Column<Location>[])
      : []),
  ];

  const body = () => {
    if (locations.initialLoading) return <TableSkeleton rows={4} columns={4} />;
    if (locations.error) return <ErrorState error={locations.error} onRetry={locations.refetch} />;

    const items = locations.data ?? [];
    if (items.length === 0) {
      return (
        <EmptyState
          title="No locations yet"
          description="A location is a place inside a warehouse: a rack, a room, a shelf."
          action={
            isManager ? (
              <Button variant="primary" onClick={() => setCreating(true)}>
                New Location
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
        rowKey={(location) => location.id}
        caption="Internal locations"
      />
    );
  };

  return (
    <>
      <ControlPanel
        title="Locations"
        subtitle="Where stock sits inside a warehouse"
        actions={
          isManager ? (
            <Button variant="primary" size="sm" onClick={() => setCreating(true)}>
              New
            </Button>
          ) : undefined
        }
        filters={
          <label className="flex items-center gap-2 text-xs text-ink-muted">
            Warehouse
            <Select
              value={warehouseFilter}
              placeholder="All"
              className="odoo-input w-44"
              onChange={(event) => setWarehouseFilter(event.target.value)}
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

      <div className="p-4">
        <div className="sheet overflow-hidden">{body()}</div>
      </div>

      {creating && (
        <LocationDialog
          onClose={() => setCreating(false)}
          onSaved={() => {
            setCreating(false);
            locations.refetch();
          }}
        />
      )}

      <ConfirmDialog
        open={archiving !== null}
        title={`Archive ${archiving?.code ?? ""}?`}
        message="This is refused while the location still holds stock. Past documents and the ledger are unaffected."
        confirmLabel="Archive"
        destructive
        pending={archive.pending}
        onConfirm={() => archiving && void archive.run(archiving.id)}
        onClose={() => setArchiving(null)}
      />
    </>
  );
}

function LocationDialog({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const { notify } = useToast();
  const warehouses = useWarehouses();
  const [formError, setFormError] = useState<string>();

  const form = useForm({
    schema: locationSchema,
    initialValues: { name: "", short_code: "", warehouse_id: "" },
    onSubmit: async (values, helpers) => {
      setFormError(undefined);
      try {
        const saved = await locationApi.create(values);
        notify("success", `${saved.code} created`);
        onSaved();
      } catch (error) {
        const unplaced = isApiError(error) ? helpers.applyServerErrors(error) : [];
        setFormError(unplaced[0] ?? messageOf(error));
      }
    },
  });

  return (
    <Modal
      open
      title="New location"
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

        <Field label="Warehouse" error={form.errorFor("warehouse_id")} required>
          {(aria) => (
            <Select {...aria} {...form.field("warehouse_id")} placeholder="Select a warehouse">
              {(warehouses.data ?? []).map((warehouse) => (
                <option key={warehouse.id} value={warehouse.id}>
                  {warehouse.name} ({warehouse.short_code})
                </option>
              ))}
            </Select>
          )}
        </Field>

        <Field label="Name" error={form.errorFor("name")} required>
          {(aria) => <Input {...aria} {...form.field("name")} autoFocus placeholder="Rack A" />}
        </Field>

        <Field
          label="Short code"
          error={form.errorFor("short_code")}
          hint="Shown as WH/<code> on documents"
          required
        >
          {(aria) => <Input {...aria} {...form.field("short_code")} placeholder="Stock" />}
        </Field>

        <button type="submit" className="hidden" aria-hidden tabIndex={-1} />
      </form>
    </Modal>
  );
}
