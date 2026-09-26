import type { Metadata } from "next";
import { ProductCreateForm } from "@/components/products/ProductForm";

export const metadata: Metadata = { title: "New Product" };

export default function NewProductPage() {
  return <ProductCreateForm />;
}
