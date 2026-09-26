"use client";

import { useState } from "react";
import { FormAlert } from "@/components/auth/FormAlert";
import {
  Badge,
  Button,
  ControlPanel,
  DataTable,
  EmptyState,
  ErrorState,
  Field,
  FilterChip,
  Input,
  Modal,
  Select,
  SearchInput,
  TableSkeleton,
  Textarea,
  type Column,
} from "@/components/ui";
import { isApiError, messageOf, partnerApi } from "@/lib/api";
import { useForm } from "@/lib/hooks/useForm";
import { useResource } from "@/lib/hooks/useResource";
import { useUrlFilters } from "@/lib/hooks/useUrlFilters";
import { useToast } from "@/providers/ToastProvider";
import { partnerSchema } from "@/lib/validation/schemas";
import type { Page, Partner, PartnerType } from "@/types/api";

const TYPE_LABELS: Record<PartnerType, string> = {
  vendor: "Vendor",
  customer: "Customer",
  both: "Vendor & Customer",
};

/**
 * Vendors and customers.
 *
 * A contact marked `both` can appear on a receipt and on a delivery; the server checks
 * that a contact may act in the role a document needs, so the two lists here are a
 * convenience rather than the rule.
 */
export function ContactManager() {
  const filters = useUrlFilters();
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Partner | null>(null);

  const query = filters.get("q") ?? "";
  const type = filters.get("type") as PartnerType | undefined;

  const partners = useResource<Page<Partner>>(
    () => partnerApi.list({ q: query || undefined, type, page_size: 50 }),
    [query, type],
  );

  const columns: Column<Partner>[] = [
    { key: "name", header: "Name", cell: (partner) => partner.name },
    {
      key: "type",
      header: "Type",
      cell: (partner) => (
        <Badge
          className={
            partner.type === "vendor"
              ? "bg-sky-100 text-sky-800 ring-sky-300"
              : partner.type === "customer"
                ? "bg-emerald-100 text-emerald-800 ring-emerald-300"
                : "bg-brand-100 text-brand-700 ring-brand-200"
          }
        >
          {TYPE_LABELS[partner.type]}
        </Badge>
      ),
    },
    {
      key: "email",
      header: "Email",
      secondary: true,
      cell: (partner) => partner.email ?? <span className="text-ink-muted">—</span>,
    },
    {
      key: "phone",
      header: "Phone",
      secondary: true,
      cell: (partner) => partner.phone ?? <span className="text-ink-muted">—</span>,
    },
    {
      key: "actions",
      header: <span className="sr-only">Actions</span>,
      align: "right",
      cell: (partner) => (
        <Button variant="ghost" size="sm" onClick={() => setEditing(partner)}>
          Edit
        </Button>
      ),
    },
  ];

  const body = () => {
    if (partners.initialLoading) return <TableSkeleton rows={4} columns={5} />;
    if (partners.error) return <ErrorState error={partners.error} onRetry={partners.refetch} />;

    const items = partners.data?.items ?? [];
    if (items.length === 0) {
      return (
        <EmptyState
          title={filters.active ? "No contacts match those filters" : "No contacts yet"}
          description={
            filters.active ? undefined : "Receipts need a vendor; deliveries need a customer."
          }
          action={
            filters.active ? (
              <Button onClick={filters.clear}>Clear filters</Button>
            ) : (
              <Button variant="primary" onClick={() => setCreating(true)}>
                New Contact
              </Button>
            )
          }
        />
      );
    }

    return (
      <DataTable
        columns={columns}
        rows={items}
        rowKey={(partner) => partner.id}
        caption="Vendors and customers"
      />
    );
  };

  return (
    <>
      <ControlPanel
        title="Contacts"
        subtitle="The vendors goods come from and the customers they go to"
        actions={
          <Button variant="primary" size="sm" onClick={() => setCreating(true)}>
            New
          </Button>
        }
        search={
          <SearchInput
            value={query}
            onChange={(value) => filters.set({ q: value })}
            placeholder="Search a contact"
          />
        }
        filters={
          <>
            {(["vendor", "customer"] as const).map((value) => (
              <FilterChip
                key={value}
                active={type === value}
                onClick={() => filters.set({ type: type === value ? undefined : value })}
              >
                {TYPE_LABELS[value]}s
              </FilterChip>
            ))}
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

      {(creating || editing) && (
        <ContactDialog
          key={editing?.id ?? "new"}
          partner={editing ?? undefined}
          onClose={() => {
            setCreating(false);
            setEditing(null);
          }}
          onSaved={() => {
            setCreating(false);
            setEditing(null);
            partners.refetch();
          }}
        />
      )}
    </>
  );
}

function ContactDialog({
  partner,
  onClose,
  onSaved,
}: {
  partner?: Partner;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { notify } = useToast();
  const [formError, setFormError] = useState<string>();

  const form = useForm({
    schema: partnerSchema,
    initialValues: {
      name: partner?.name ?? "",
      type: partner?.type ?? "vendor",
      email: partner?.email ?? "",
      phone: partner?.phone ?? "",
      address: partner?.address ?? "",
    },
    onSubmit: async (values, helpers) => {
      setFormError(undefined);
      try {
        const saved = partner
          ? await partnerApi.update(partner.id, values)
          : await partnerApi.create(values);
        notify("success", `${saved.name} saved`);
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
      title={partner ? `Edit ${partner.name}` : "New contact"}
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
          {(aria) => <Input {...aria} {...form.field("name")} autoFocus />}
        </Field>

        <Field label="Type" error={form.errorFor("type")} required>
          {(aria) => (
            <Select {...aria} {...form.field("type")}>
              {(Object.keys(TYPE_LABELS) as PartnerType[]).map((value) => (
                <option key={value} value={value}>
                  {TYPE_LABELS[value]}
                </option>
              ))}
            </Select>
          )}
        </Field>

        <Field label="Email" error={form.errorFor("email")}>
          {(aria) => <Input {...aria} {...form.field("email")} type="email" />}
        </Field>

        <Field label="Phone" error={form.errorFor("phone")}>
          {(aria) => <Input {...aria} {...form.field("phone")} />}
        </Field>

        <Field label="Address" error={form.errorFor("address")}>
          {(aria) => <Textarea {...aria} {...form.field("address")} rows={2} />}
        </Field>

        <button type="submit" className="hidden" aria-hidden tabIndex={-1} />
      </form>
    </Modal>
  );
}
