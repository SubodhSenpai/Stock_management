import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 px-4 text-center">
      <p className="text-5xl font-semibold text-brand-200">404</p>
      <h1 className="text-lg font-semibold text-ink">This page does not exist</h1>
      <p className="max-w-sm text-sm text-ink-muted">
        The link may be out of date, or the document may have been removed.
      </p>
      <Link
        href="/dashboard"
        className="mt-2 rounded bg-accent-500 px-4 py-2 text-sm font-medium text-white hover:bg-accent-600"
      >
        Back to the dashboard
      </Link>
    </div>
  );
}
