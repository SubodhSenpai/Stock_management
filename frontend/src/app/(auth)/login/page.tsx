import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { LoginForm } from "@/components/auth/LoginForm";

export const metadata: Metadata = { title: "Sign in" };

export default function LoginPage() {
  return (
    <>
      <header className="mb-6">
        <h1 className="text-xl font-semibold text-brand-700">Sign in</h1>
        <p className="mt-1 text-sm text-ink-muted">Welcome back. Pick up where you left off.</p>
      </header>

      {/* The form reads `?next=` to return the user to the page they asked for. */}
      <Suspense fallback={<div className="h-64" />}>
        <LoginForm />
      </Suspense>

      <p className="mt-6 border-t border-line pt-4 text-center text-sm text-ink-muted">
        No account yet?{" "}
        <Link href="/signup" className="font-medium text-accent-600 hover:underline">
          Sign up
        </Link>
      </p>
    </>
  );
}
