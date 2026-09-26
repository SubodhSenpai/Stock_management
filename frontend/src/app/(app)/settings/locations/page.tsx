import type { Metadata } from "next";
import { LocationManager } from "@/components/settings/LocationManager";

export const metadata: Metadata = { title: "Locations" };

export default function LocationsPage() {
  return <LocationManager />;
}
