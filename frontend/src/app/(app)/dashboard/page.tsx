import type { Metadata } from "next";
import { Suspense } from "react";
import { Dashboard } from "@/components/dashboard/Dashboard";

export const metadata: Metadata = { title: "Dashboard" };

export default function DashboardPage() {
  // The warehouse filter is read from the query string, which needs a Suspense boundary.
  return (
    <Suspense fallback={null}>
      <Dashboard />
    </Suspense>
  );
}
