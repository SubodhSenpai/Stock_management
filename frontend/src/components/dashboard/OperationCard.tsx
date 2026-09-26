"use client";

import Link from "next/link";
import { cn } from "@/lib/cn";
import { configForType } from "@/lib/config/operations";
import type { OperationCard as CardData } from "@/types/api";

/**
 * A document-type card, as on the mockup's dashboard.
 *
 * The big number is what can be acted on right now; the small ones are the reasons to
 * look. Every figure is a link into the list with the matching filter already applied,
 * so the card is a way in rather than a read-out.
 */
export function OperationCard({ card }: { card: CardData }) {
  const config = configForType(card.type);
  const base = `/operations/${config.slug}`;

  const breakdown = [
    { label: "Late", value: card.late, href: `${base}?late=true`, tone: "danger" as const },
    { label: "Waiting", value: card.waiting, href: `${base}?status=waiting`, tone: "warn" as const },
    { label: "Upcoming", value: card.upcoming, href: `${base}`, tone: "muted" as const },
  ].filter((entry) => entry.value > 0 || entry.label !== "Waiting");

  return (
    <article className="sheet flex flex-col p-4 transition-shadow hover:shadow-md">
      <header className="flex items-start justify-between gap-3">
        <h3 className="text-sm font-semibold text-brand-700">{config.title}</h3>
        <Link
          href={`${base}/new`}
          className="rounded border border-line px-2 py-0.5 text-xs text-ink-muted transition-colors hover:border-accent-500 hover:text-accent-600"
        >
          New
        </Link>
      </header>

      <Link href={`${base}?status=ready`} className="mt-3 inline-flex items-baseline gap-2">
        <span className="text-3xl font-semibold text-ink">{card.to_process}</span>
        <span className="text-sm text-ink-muted">
          to {card.type === "receipt" ? "receive" : card.type === "delivery" ? "deliver" : "process"}
        </span>
      </Link>

      <dl className="mt-3 flex flex-wrap gap-x-5 gap-y-1 border-t border-line pt-3 text-xs">
        {breakdown.map((entry) => (
          <div key={entry.label}>
            <Link href={entry.href} className="group flex items-baseline gap-1.5">
              <dd
                className={cn(
                  "font-semibold",
                  entry.tone === "danger" && entry.value > 0 && "text-rose-600",
                  entry.tone === "warn" && entry.value > 0 && "text-amber-600",
                  (entry.tone === "muted" || entry.value === 0) && "text-ink",
                )}
              >
                {entry.value}
              </dd>
              <dt className="text-ink-muted group-hover:text-accent-600 group-hover:underline">
                {entry.label}
              </dt>
            </Link>
          </div>
        ))}
      </dl>

      <Link
        href={base}
        className="mt-3 text-xs text-accent-600 hover:underline"
        aria-label={`All ${config.title.toLowerCase()}`}
      >
        {card.pending} open document{card.pending === 1 ? "" : "s"} →
      </Link>
    </article>
  );
}
