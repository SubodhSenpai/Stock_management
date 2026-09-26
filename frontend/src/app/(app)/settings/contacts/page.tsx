import type { Metadata } from "next";
import { Suspense } from "react";
import { ContactManager } from "@/components/settings/ContactManager";

export const metadata: Metadata = { title: "Contacts" };

export default function ContactsPage() {
  return (
    <Suspense fallback={null}>
      <ContactManager />
    </Suspense>
  );
}
