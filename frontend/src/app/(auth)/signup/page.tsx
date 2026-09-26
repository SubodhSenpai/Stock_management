import type { Metadata } from "next";
import Link from "next/link";
import { SignupForm } from "@/components/auth/SignupForm";

export const metadata: Metadata = { title: "Sign up" };

export default function SignupPage() {
  return (
    <>
      <header className="mb-6">
        <h1 className="text-xl font-semibold text-brand-700">Create your account</h1>
        <p className="mt-1 text-sm text-ink-muted">It takes a minute.</p>
      </header>

      <SignupForm />

      <p className="mt-6 border-t border-line pt-4 text-center text-sm text-ink-muted">
        Already registered?{" "}
        <Link href="/login" className="font-medium text-accent-600 hover:underline">
          Sign in
        </Link>
      </p>
    </>
  );
}
