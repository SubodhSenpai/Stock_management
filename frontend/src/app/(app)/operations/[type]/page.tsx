import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { OperationList } from "@/components/operations/OperationList";
import { OPERATION_CONFIGS, OPERATION_SLUGS, isOperationSlug } from "@/lib/config/operations";

/** One route serves all four document types; the slug picks the configuration. */
export function generateStaticParams() {
  return OPERATION_SLUGS.map((type) => ({ type }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ type: string }>;
}): Promise<Metadata> {
  const { type } = await params;
  if (!isOperationSlug(type)) return { title: "Operations" };
  return { title: OPERATION_CONFIGS[type].title };
}

export default async function OperationListPage({
  params,
}: {
  params: Promise<{ type: string }>;
}) {
  const { type } = await params;
  if (!isOperationSlug(type)) notFound();

  return <OperationList config={OPERATION_CONFIGS[type]} />;
}
