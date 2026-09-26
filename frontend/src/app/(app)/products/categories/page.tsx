import type { Metadata } from "next";
import { CategoryManager } from "@/components/products/CategoryManager";

export const metadata: Metadata = { title: "Categories" };

export default function CategoriesPage() {
  return <CategoryManager />;
}
