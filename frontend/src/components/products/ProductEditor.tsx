"use client";

import { ErrorState, TableSkeleton } from "@/components/ui";
import { catalogApi } from "@/lib/api";
import { useResource } from "@/lib/hooks/useResource";
import type { Product } from "@/types/api";
import { ProductEditForm } from "./ProductForm";

/** Loads the product the edit form starts from. */
export function ProductEditor({ productId }: { productId: number }) {
  const resource = useResource<Product>(() => catalogApi.getProduct(productId), [productId]);

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

  return resource.data ? <ProductEditForm product={resource.data} /> : null;
}
