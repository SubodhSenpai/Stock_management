import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ProductDetail } from "@/components/products/ProductDetail";

export const metadata: Metadata = { title: "Product" };

export default async function ProductDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const productId = Number(id);
  if (!Number.isInteger(productId) || productId <= 0) notFound();

  return <ProductDetail productId={productId} />;
}
