import type { Metadata } from "next";
import { Suspense } from "react";
import { MoveHistory } from "@/components/stock/MoveHistory";

export const metadata: Metadata = { title: "Move History" };

export default function MovesPage() {
  return (
    <Suspense fallback={null}>
      <MoveHistory />
    </Suspense>
  );
}
