import type { Metadata } from "next";
import { Suspense } from "react";
import { StockTable } from "@/components/stock/StockTable";

export const metadata: Metadata = { title: "Stock" };

export default function StockPage() {
  return (
    <Suspense fallback={null}>
      <StockTable />
    </Suspense>
  );
}
