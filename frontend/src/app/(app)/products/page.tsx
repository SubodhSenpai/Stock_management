import type { Metadata } from "next";
import { Suspense } from "react";
import { ProductList } from "@/components/products/ProductList";

export const metadata: Metadata = { title: "Products" };

export default function ProductsPage() {
  return (
    <Suspense fallback={null}>
      <ProductList />
    </Suspense>
  );
}
