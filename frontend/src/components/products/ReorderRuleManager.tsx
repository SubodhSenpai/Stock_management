"use client";

import { useState } from "react";
import { FormAlert } from "@/components/auth/FormAlert";
import { ProductPicker } from "@/components/common/ProductPicker";
import {
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
import { catalogApi, isApiError, messageOf } from "@/lib/api";
import { formatQuantity, productLabel } from "@/lib/format";
import { useAction } from "@/lib/hooks/useAction";
import { useForm } from "@/lib/hooks/useForm";
import { useResource } from "@/lib/hooks/useResource";
import { useWarehouses } from "@/lib/hooks/useReferenceData";
import { useSession } from "@/providers/SessionProvider";
import { useToast } from "@/providers/ToastProvider";
import { reorderRuleSchema } from "@/lib/validation/schemas";
import type { ProductBrief, ReorderRule, Warehouse } from "@/types/api";

/**
 * Reordering rules: the minimum a product should not fall below in a warehouse, and
 * the level to restock to.
 *
 * These are what put a product on the dashboard's "needs reordering" list, so the rule
 * screen and that list are two views of the same setting.
 */
export function ReorderRuleManager() {
  const { isManager } = useSession();
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState<ReorderRule | null>(null);

  const rules = useResource<ReorderRule[]>(() => catalogApi.listReorderRules(), []);
  const warehouses = useWarehouses();

  // Rules carry ids rather than names, so the labels are resolved from the lists the
  // page already has instead of asking the server per row.
  const warehouseNames = new Map(
    (warehouses.data ?? []).map((warehouse: Warehouse) => [warehouse.id, warehouse.name]),
  );

  const remove = useAction((id: number) => catalogApi.deleteReorderRule(id), {
    successMessage: () => "Rule deleted",
    onSuccess: () => {
      setDeleting(null);
      rules.refetch();
    },
  });

  const columns: Column<ReorderRule>[] = [
    {
      key: "product",
      header: "Product",
      cell: (rule) => <ProductName productId={rule.product_id} />,
    },
    {
      key: "warehouse",
      header: "Warehouse",
      cell: (rule) => warehouseNames.get(rule.warehouse_id) ?? `#${rule.warehouse_id}`,
    },
    {
      key: "min",
      header: "Minimum",
      align: "right",
      cell: (rule) => formatQuantity(rule.min_quantity),
    },
    {
      key: "max",
      header: "Restock to",
      align: "right",
      cell: (rule) => formatQuantity(rule.max_quantity),
    },
    ...(isManager
      ? ([
          {
            key: "actions",
            header: <span className="sr-only">Actions</span>,
            align: "right",
            cell: (rule: ReorderRule) => (
              <Button variant="ghost" size="sm" onClick={() => setDeleting(rule)}>
                Delete
              </Button>
            ),
          },
        ] as Column<ReorderRule>[])
      : []),
  ];

  const body = () => {
    if (rules.initialLoading) return <TableSkeleton rows={4} columns={5} />;
    if (rules.error) return <ErrorState error={rules.error} onRetry={rules.refetch} />;

    const items = rules.data ?? [];
    if (items.length === 0) {
      return (
        <EmptyState
          title="No reordering rules yet"
          description="A rule flags a product on the dashboard once its stock reaches the minimum."
          action={
            isManager ? (
              <Button variant="primary" onClick={() => setCreating(true)}>
                New Rule
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
        rowKey={(rule) => rule.id}
        caption="Reordering rules"
      />
    );
  };

  return (
    <>
      <ControlPanel
        title="Reordering Rules"
        subtitle="Products fall onto the dashboard's reorder list when they reach the minimum"
        actions={
          isManager ? (
            <Button variant="primary" size="sm" onClick={() => setCreating(true)}>
              New
            </Button>
          ) : undefined
        }
      />

      <div className="p-4">
        <div className="sheet overflow-hidden">{body()}</div>
      </div>

      {creating && (
        <ReorderRuleDialog
          onClose={() => setCreating(false)}
          onCreated={() => {
            setCreating(false);
            rules.refetch();
          }}
        />
      )}

      <ConfirmDialog
        open={deleting !== null}
        title="Delete this rule?"
        message="The product will no longer be flagged when it runs low. Stock is unaffected."
        confirmLabel="Delete"
        destructive
        pending={remove.pending}
        onConfirm={() => deleting && void remove.run(deleting.id)}
        onClose={() => setDeleting(null)}
      />
    </>
  );
}

/** Resolves one product's name for a rule row. */
function ProductName({ productId }: { productId: number }) {
  const product = useResource(() => catalogApi.getProduct(productId), [productId]);
  if (!product.data) return <span className="text-ink-muted">#{productId}</span>;
  return <span>{productLabel(product.data)}</span>;
}

function ReorderRuleDialog({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const { notify } = useToast();
  const warehouses = useWarehouses();
  const [product, setProduct] = useState<ProductBrief | null>(null);
  const [formError, setFormError] = useState<string>();

  const form = useForm({
    schema: reorderRuleSchema,
    initialValues: {
      product_id: "",
      warehouse_id: "",
      min_quantity: "0",
      max_quantity: "0",
    },
    onSubmit: async (values, helpers) => {
      setFormError(undefined);
      try {
        await catalogApi.createReorderRule(values);
        notify("success", "Rule saved");
        onCreated();
      } catch (error) {
        const unplaced = isApiError(error) ? helpers.applyServerErrors(error) : [];
        setFormError(unplaced[0] ?? messageOf(error));
      }
    },
  });

  return (
    <Modal
      open
      title="New reordering rule"
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

        <Field label="Product" error={form.errorFor("product_id")} required>
          {(aria) => (
            <ProductPicker
              id={aria.id}
              aria-describedby={aria["aria-describedby"]}
              invalid={Boolean(form.errorFor("product_id"))}
              value={product}
              onSelect={(chosen) => {
                setProduct(chosen);
                form.setValue("product_id", String(chosen.id));
              }}
            />
          )}
        </Field>

        <Field label="Warehouse" error={form.errorFor("warehouse_id")} required>
          {(aria) => (
            <Select {...aria} {...form.field("warehouse_id")} placeholder="Select a warehouse">
              {(warehouses.data ?? []).map((warehouse) => (
                <option key={warehouse.id} value={warehouse.id}>
                  {warehouse.name}
                </option>
              ))}
            </Select>
          )}
        </Field>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field
            label="Minimum"
            error={form.errorFor("min_quantity")}
            hint="Flag the product at or below this"
            required
          >
            {(aria) => <Input {...aria} {...form.field("min_quantity")} inputMode="decimal" />}
          </Field>

          <Field
            label="Restock to"
            error={form.errorFor("max_quantity")}
            hint="Used to suggest an order quantity"
            required
          >
            {(aria) => <Input {...aria} {...form.field("max_quantity")} inputMode="decimal" />}
          </Field>
        </div>

        <button type="submit" className="hidden" aria-hidden tabIndex={-1} />
      </form>
    </Modal>
  );
}
