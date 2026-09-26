"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { Button, Field, Input } from "@/components/ui";
import { authApi, isApiError, messageOf } from "@/lib/api";
import { useForm } from "@/lib/hooks/useForm";
import { loginSchema } from "@/lib/validation/schemas";
import { FormAlert } from "./FormAlert";

/**
 * Sign in.
 *
 * The response sets two httpOnly cookies; nothing is kept in JavaScript, so there is no
 * token on the page for a script to read. `router.refresh()` re-runs the server layout,
 * which then sees the new session.
 */
export function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();

  // Only a path within this app: an absolute URL here would be an open redirect.
  const requested = params.get("next");
  const next =
    requested?.startsWith("/") && !requested.startsWith("//") ? requested : "/dashboard";

  const [formError, setFormError] = useState<string>();

  const form = useForm({
    schema: loginSchema,
    initialValues: { login_id: "", password: "" },
    onSubmit: async (values, helpers) => {
      setFormError(undefined);
      try {
        await authApi.login(values);
        router.replace(next);
        router.refresh();
      } catch (error) {
        // A failed sign-in carries no field details on purpose: the message must not
        // reveal whether it was the login id or the password that was wrong.
        const unplaced = isApiError(error) ? helpers.applyServerErrors(error) : [];
        setFormError(unplaced[0] ?? messageOf(error));
      }
    },
  });

  return (
    <form onSubmit={form.handleSubmit} method="post" noValidate className="space-y-5">
      <FormAlert message={formError} />

      <Field label="Login ID or Email" error={form.errorFor("login_id")} required>
        {(aria) => (
          <Input
            {...aria}
            {...form.field("login_id")}
            autoComplete="username"
            autoFocus
            placeholder="manager1 or user@example.com"
          />
        )}
      </Field>

      <Field label="Password" error={form.errorFor("password")} required>
        {(aria) => (
          <Input
            {...aria}
            {...form.field("password")}
            type="password"
            autoComplete="current-password"
          />
        )}
      </Field>

      <div className="flex justify-end">
        <Link href="/forgot-password" className="text-xs text-accent-600 hover:underline">
          Forgot password?
        </Link>
      </div>

      <Button type="submit" variant="primary" loading={form.submitting} className="w-full">
        Sign in
      </Button>
    </form>
  );
}
