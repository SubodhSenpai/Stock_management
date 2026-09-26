import type { Metadata } from "next";
import { ProfilePanel } from "@/components/settings/ProfilePanel";

export const metadata: Metadata = { title: "My Profile" };

export default function ProfilePage() {
  return <ProfilePanel />;
}
