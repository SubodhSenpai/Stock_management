import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ProductEditor } from "@/components/products/ProductEditor";

export const metadata: Metadata = { title: "Edit Product" };

export default async function EditProductPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const productId = Number(id);
  if (!Number.isInteger(productId) || productId <= 0) notFound();

  return <ProductEditor productId={productId} />;
}
