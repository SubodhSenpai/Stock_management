import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { OperationPrint } from "@/components/operations/OperationPrint";
import { OPERATION_CONFIGS, isOperationSlug } from "@/lib/config/operations";

export const metadata: Metadata = { title: "Print" };

export default async function PrintOperationPage({
  params,
}: {
  params: Promise<{ type: string; id: string }>;
}) {
  const { type, id } = await params;
  const operationId = Number(id);
  if (!isOperationSlug(type) || !Number.isInteger(operationId) || operationId <= 0) notFound();

  return <OperationPrint config={OPERATION_CONFIGS[type]} operationId={operationId} />;
}
