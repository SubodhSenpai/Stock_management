"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button, Field, Input } from "@/components/ui";
import { authApi, isApiError, messageOf } from "@/lib/api";
import { useForm } from "@/lib/hooks/useForm";
import {
  forgotPasswordSchema,
  resetPasswordSchema,
  verifyOtpSchema,
} from "@/lib/validation/schemas";
import { FormAlert } from "./FormAlert";
import { PasswordRules } from "./PasswordRules";

/**
 * Resetting a forgotten password, in three steps: ask for a code, prove you received
 * it, then choose a new password.
 *
 * The email is kept in component state between steps rather than in the URL, so a
 * half-finished reset cannot be resumed from a shared link or a browser history entry.
 */
type Step = "request" | "verify" | "reset";

export function ForgotPasswordFlow() {
  const [step, setStep] = useState<Step>("request");
  const [email, setEmail] = useState("");
  const [resetToken, setResetToken] = useState("");

  if (step === "verify") {
    return (
      <VerifyStep
        email={email}
        onVerified={(token) => {
          setResetToken(token);
          setStep("reset");
        }}
        onBack={() => setStep("request")}
      />
    );
  }

  if (step === "reset") {
    return <ResetStep resetToken={resetToken} />;
  }

  return (
    <RequestStep
      onSent={(address) => {
        setEmail(address);
        setStep("verify");
      }}
    />
  );
}

/** Step 1. The reply is the same whether or not the address is registered. */
function RequestStep({ onSent }: { onSent: (email: string) => void }) {
  const [formError, setFormError] = useState<string>();

  const form = useForm({
    schema: forgotPasswordSchema,
    initialValues: { email: "" },
    onSubmit: async (values, helpers) => {
      setFormError(undefined);
      try {
        await authApi.forgotPassword(values.email);
        onSent(values.email);
      } catch (error) {
        const unplaced = isApiError(error) ? helpers.applyServerErrors(error) : [];
        setFormError(unplaced[0] ?? messageOf(error));
      }
    },
  });

  return (
    <form onSubmit={form.handleSubmit} method="post" noValidate className="space-y-5">
      <StepHeader
        step={1}
        title="Forgot your password?"
        description="Enter your email and we'll send a 6-digit verification code."
      />
      <FormAlert message={formError} />

      <Field label="Email" error={form.errorFor("email")} required>
        {(aria) => (
          <Input {...aria} {...form.field("email")} type="email" autoComplete="email" autoFocus />
        )}
      </Field>

      <Button type="submit" variant="primary" loading={form.submitting} className="w-full">
        Send code
      </Button>

      <BackToSignIn />
    </form>
  );
}

/** Step 2. Exchange the code for a short-lived reset token. */
function VerifyStep({
  email,
  onVerified,
  onBack,
}: {
  email: string;
  onVerified: (token: string) => void;
  onBack: () => void;
}) {
  const [formError, setFormError] = useState<string>();

  const form = useForm({
    schema: verifyOtpSchema,
    initialValues: { otp: "" },
    onSubmit: async (values, helpers) => {
      setFormError(undefined);
      try {
        const { reset_token } = await authApi.verifyOtp(email, values.otp);
        onVerified(reset_token);
      } catch (error) {
        const unplaced = isApiError(error) ? helpers.applyServerErrors(error) : [];
        setFormError(unplaced[0] ?? messageOf(error));
      }
    },
  });

  return (
    <form onSubmit={form.handleSubmit} method="post" noValidate className="space-y-5">
      <StepHeader
        step={2}
        title="Enter the code"
        description={`If ${email} is registered, a 6-digit code is on its way. It expires in 10 minutes.`}
      />
      <FormAlert message={formError} />

      <Field label="Verification code" error={form.errorFor("otp")} required>
        {(aria) => (
          <Input
            {...aria}
            {...form.field("otp")}
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={6}
            autoFocus
            className="odoo-input text-center text-2xl tracking-[0.5em]"
            placeholder="000000"
          />
        )}
      </Field>

      <Button type="submit" variant="primary" loading={form.submitting} className="w-full">
        Verify
      </Button>

      <button
        type="button"
        onClick={onBack}
        className="w-full text-center text-xs text-ink-muted hover:text-accent-600 hover:underline"
      >
        Use a different email
      </button>
    </form>
  );
}

/** Step 3. Setting the password also ends every existing session for that user. */
function ResetStep({ resetToken }: { resetToken: string }) {
  const router = useRouter();
  const [formError, setFormError] = useState<string>();
  const [done, setDone] = useState(false);

  const form = useForm({
    schema: resetPasswordSchema,
    initialValues: { password: "", confirm_password: "" },
    onSubmit: async (values, helpers) => {
      setFormError(undefined);
      try {
        await authApi.resetPassword({ reset_token: resetToken, ...values });
        setDone(true);
        setTimeout(() => router.replace("/login"), 1500);
      } catch (error) {
        const unplaced = isApiError(error) ? helpers.applyServerErrors(error) : [];
        setFormError(unplaced[0] ?? messageOf(error));
      }
    },
  });

  if (done) {
    return (
      <div className="space-y-4 text-center">
        <p className="text-3xl" aria-hidden>
          ✓
        </p>
        <h1 className="text-lg font-semibold text-brand-700">Password updated</h1>
        <p className="text-sm text-ink-muted">
          Every other session has been signed out. Taking you to the sign-in page.
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={form.handleSubmit} method="post" noValidate className="space-y-4">
      <StepHeader step={3} title="Choose a new password" />
      <FormAlert message={formError} />

      <Field label="New password" error={form.errorFor("password")} required>
        {(aria) => (
          <Input
            {...aria}
            {...form.field("password")}
            type="password"
            autoComplete="new-password"
            autoFocus
          />
        )}
      </Field>

      <PasswordRules value={String(form.values.password ?? "")} />

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
        Set password
      </Button>
    </form>
  );
}

function StepHeader({
  step,
  title,
  description,
}: {
  step: number;
  title: string;
  description?: string;
}) {
  return (
    <header>
      <p className="text-xs font-medium uppercase tracking-wide text-accent-600">
        Step {step} of 3
      </p>
      <h1 className="mt-1 text-xl font-semibold text-brand-700">{title}</h1>
      {description && <p className="mt-1 text-sm text-ink-muted">{description}</p>}
    </header>
  );
}

function BackToSignIn() {
  return (
    <p className="text-center text-sm text-ink-muted">
      Remembered it?{" "}
      <Link href="/login" className="font-medium text-accent-600 hover:underline">
        Sign in
      </Link>
    </p>
  );
}
