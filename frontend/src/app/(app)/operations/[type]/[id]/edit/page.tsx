import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { OperationEditor } from "@/components/operations/OperationEditor";
import { OPERATION_CONFIGS, isOperationSlug } from "@/lib/config/operations";

export const metadata: Metadata = { title: "Edit" };

export default async function EditOperationPage({
  params,
}: {
  params: Promise<{ type: string; id: string }>;
}) {
  const { type, id } = await params;
  const operationId = Number(id);
  if (!isOperationSlug(type) || !Number.isInteger(operationId) || operationId <= 0) notFound();

  return <OperationEditor config={OPERATION_CONFIGS[type]} operationId={operationId} />;
}
