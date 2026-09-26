import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { OperationDetail } from "@/components/operations/OperationDetail";
import { OPERATION_CONFIGS, isOperationSlug } from "@/lib/config/operations";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ type: string; id: string }>;
}): Promise<Metadata> {
  const { type } = await params;
  if (!isOperationSlug(type)) return { title: "Document" };
  return { title: OPERATION_CONFIGS[type].singular };
}

export default async function OperationDetailPage({
  params,
}: {
  params: Promise<{ type: string; id: string }>;
}) {
  const { type, id } = await params;
  const operationId = Number(id);
  if (!isOperationSlug(type) || !Number.isInteger(operationId) || operationId <= 0) notFound();

  return <OperationDetail config={OPERATION_CONFIGS[type]} operationId={operationId} />;
}
