"use client";

import { useState } from "react";
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
  TableSkeleton,
  type Column,
} from "@/components/ui";
import { FormAlert } from "@/components/auth/FormAlert";
import { catalogApi, isApiError, messageOf } from "@/lib/api";
import { useAction } from "@/lib/hooks/useAction";
import { useForm } from "@/lib/hooks/useForm";
import { useResource } from "@/lib/hooks/useResource";
import { useSession } from "@/providers/SessionProvider";
import { useToast } from "@/providers/ToastProvider";
import { categorySchema } from "@/lib/validation/schemas";
import type { Category } from "@/types/api";

/**
 * Product categories.
 *
 * Deleting one is refused by the server while products still use it, which is reported
 * as it comes back rather than pre-empted here: the check belongs where the data is.
 */
export function CategoryManager() {
  const { isManager } = useSession();
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState<Category | null>(null);

  const categories = useResource<Category[]>(() => catalogApi.listCategories(), []);

  const remove = useAction((id: number) => catalogApi.deleteCategory(id), {
    successMessage: () => "Category deleted",
    onSuccess: () => {
      setDeleting(null);
      categories.refetch();
    },
  });

  const columns: Column<Category>[] = [
    { key: "name", header: "Name", cell: (category) => category.name },
    ...(isManager
      ? ([
          {
            key: "actions",
            header: <span className="sr-only">Actions</span>,
            align: "right",
            cell: (category: Category) => (
              <Button variant="ghost" size="sm" onClick={() => setDeleting(category)}>
                Delete
              </Button>
            ),
          },
        ] as Column<Category>[])
      : []),
  ];

  const body = () => {
    if (categories.initialLoading) return <TableSkeleton rows={4} columns={2} />;
    if (categories.error) {
      return <ErrorState error={categories.error} onRetry={categories.refetch} />;
    }

    const items = categories.data ?? [];
    if (items.length === 0) {
      return (
        <EmptyState
          title="No categories yet"
          description="Categories group the catalogue so products can be filtered."
          action={
            isManager ? (
              <Button variant="primary" onClick={() => setCreating(true)}>
                New Category
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
        rowKey={(category) => category.id}
        caption="Product categories"
      />
    );
  };

  return (
    <>
      <ControlPanel
        title="Categories"
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
        <CategoryDialog
          onClose={() => setCreating(false)}
          onCreated={() => {
            setCreating(false);
            categories.refetch();
          }}
        />
      )}

      <ConfirmDialog
        open={deleting !== null}
        title={`Delete ${deleting?.name ?? ""}?`}
        message="This is refused if any product still uses the category."
        confirmLabel="Delete"
        destructive
        pending={remove.pending}
        onConfirm={() => deleting && void remove.run(deleting.id)}
        onClose={() => setDeleting(null)}
      />
    </>
  );
}

function CategoryDialog({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const { notify } = useToast();
  const [formError, setFormError] = useState<string>();

  const form = useForm({
    schema: categorySchema,
    initialValues: { name: "" },
    onSubmit: async (values, helpers) => {
      setFormError(undefined);
      try {
        const created = await catalogApi.createCategory(values.name);
        notify("success", `${created.name} added`);
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
      title="New category"
      onClose={onClose}
      size="sm"
      footer={
        <>
          <Button onClick={onClose} disabled={form.submitting}>
            Cancel
          </Button>
          <Button variant="primary" loading={form.submitting} onClick={form.handleSubmit}>
            Create
          </Button>
        </>
      }
    >
      <form onSubmit={form.handleSubmit} noValidate className="space-y-3">
        <FormAlert message={formError} />
        <Field label="Name" error={form.errorFor("name")} required>
          {(aria) => <Input {...aria} {...form.field("name")} autoFocus />}
        </Field>
        <button type="submit" className="hidden" aria-hidden tabIndex={-1} />
      </form>
    </Modal>
  );
}
