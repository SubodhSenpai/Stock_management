import type { Metadata } from "next";
import { WarehouseManager } from "@/components/settings/WarehouseManager";

export const metadata: Metadata = { title: "Warehouses" };

export default function WarehousesPage() {
  return <WarehouseManager />;
}
