"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button, Field, Input } from "@/components/ui";
import { authApi, isApiError, messageOf } from "@/lib/api";
import { useForm } from "@/lib/hooks/useForm";
import { PASSWORD_MIN_LENGTH } from "@/lib/validation/rules";
import { signupSchema } from "@/lib/validation/schemas";
import { FormAlert } from "./FormAlert";
import { PasswordRules } from "./PasswordRules";

/**
 * Create an account.
 *
 * The role is not offered: a self-service sign-up creates a staff user, and the backend
 * defaults to staff regardless of what is posted. Someone who could pick their own role
 * could grant themselves the permissions the role system exists to withhold.
 */
export function SignupForm() {
  const router = useRouter();
  const [formError, setFormError] = useState<string>();

  const form = useForm({
    schema: signupSchema,
    initialValues: {
      login_id: "",
      email: "",
      full_name: "",
      password: "",
      confirm_password: "",
    },
    onSubmit: async (values, helpers) => {
      setFormError(undefined);
      try {
        // Sign-up signs the new user in, so there is no second trip to the login page.
        await authApi.signup(values);
        router.replace("/dashboard");
        router.refresh();
      } catch (error) {
        const unplaced = isApiError(error) ? helpers.applyServerErrors(error) : [];
        setFormError(unplaced[0] ?? messageOf(error));
      }
    },
  });

  const password = String(form.values.password ?? "");

  return (
    <form onSubmit={form.handleSubmit} method="post" noValidate className="space-y-4">
      <FormAlert message={formError} />

      <Field
        label="Login ID"
        error={form.errorFor("login_id")}
        hint="6-12 characters: letters, numbers, dots and underscores"
        required
      >
        {(aria) => (
          <Input {...aria} {...form.field("login_id")} autoComplete="username" autoFocus />
        )}
      </Field>

      <Field label="Email" error={form.errorFor("email")} required>
        {(aria) => <Input {...aria} {...form.field("email")} type="email" autoComplete="email" />}
      </Field>

      <Field label="Full name" error={form.errorFor("full_name")}>
        {(aria) => <Input {...aria} {...form.field("full_name")} autoComplete="name" />}
      </Field>

      <Field
        label="Password"
        error={form.errorFor("password")}
        hint={`At least ${PASSWORD_MIN_LENGTH} characters`}
        required
      >
        {(aria) => (
          <Input
            {...aria}
            {...form.field("password")}
            type="password"
            autoComplete="new-password"
          />
        )}
      </Field>

      <PasswordRules value={password} />

      <Field label="Confirm password" error={form.errorFor("confirm_password")} required>
        {(aria) => (
          <Input
            {...aria}
            {...form.field("confirm_password")}
            type="password"
            autoComplete="new-password"
          />
        )}
      </Field>

      <Button type="submit" variant="primary" loading={form.submitting} className="w-full">
        Create account
      </Button>

      <p className="text-center text-xs text-ink-muted">
        New accounts are created as warehouse staff. A manager can change that later.
      </p>
    </form>
  );
}
