import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { OperationForm } from "@/components/operations/OperationForm";
import { OPERATION_CONFIGS, isOperationSlug } from "@/lib/config/operations";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ type: string }>;
}): Promise<Metadata> {
  const { type } = await params;
  if (!isOperationSlug(type)) return { title: "New" };
  return { title: `New ${OPERATION_CONFIGS[type].singular}` };
}

export default async function NewOperationPage({
  params,
}: {
  params: Promise<{ type: string }>;
}) {
  const { type } = await params;
  if (!isOperationSlug(type)) notFound();

  return <OperationForm config={OPERATION_CONFIGS[type]} />;
}
