import type { Metadata } from "next";
import { ReorderRuleManager } from "@/components/products/ReorderRuleManager";

export const metadata: Metadata = { title: "Reordering Rules" };

export default function ReorderRulesPage() {
  return <ReorderRuleManager />;
}
