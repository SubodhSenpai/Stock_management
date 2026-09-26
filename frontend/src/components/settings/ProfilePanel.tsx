"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { FormAlert } from "@/components/auth/FormAlert";
import { PasswordRules } from "@/components/auth/PasswordRules";
import { FormSection, FormSheet, ReadField } from "@/components/operations/FormSheet";
import { Badge, Button, ConfirmDialog, Field, Input } from "@/components/ui";
import { authApi, isApiError, messageOf } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { useAction } from "@/lib/hooks/useAction";
import { useForm } from "@/lib/hooks/useForm";
import { useSession } from "@/providers/SessionProvider";
import { useToast } from "@/providers/ToastProvider";
import { changePasswordSchema, profileSchema } from "@/lib/validation/schemas";

/**
 * The signed-in user's own account.
 *
 * Changing the password ends every other session, which is stated before it happens
 * rather than discovered afterwards on another device.
 */
export function ProfilePanel() {
  const { user, isManager, refresh, signOut } = useSession();
  const router = useRouter();
  const { notify } = useToast();

  const [profileError, setProfileError] = useState<string>();
  const [passwordError, setPasswordError] = useState<string>();
  const [confirmingSignOutAll, setConfirmingSignOutAll] = useState(false);

  const profileForm = useForm({
    schema: profileSchema,
    initialValues: { full_name: user.full_name ?? "", email: user.email },
    onSubmit: async (values, helpers) => {
      setProfileError(undefined);
      try {
        await authApi.updateProfile(values);
        await refresh();
        notify("success", "Profile updated");
        router.refresh();
      } catch (error) {
        const unplaced = isApiError(error) ? helpers.applyServerErrors(error) : [];
        setProfileError(unplaced[0] ?? messageOf(error));
      }
    },
  });

  const passwordForm = useForm({
    schema: changePasswordSchema,
    initialValues: { current_password: "", password: "", confirm_password: "" },
    onSubmit: async (values, helpers) => {
      setPasswordError(undefined);
      try {
        await authApi.changePassword(values);
        passwordForm.reset();
        notify(
          "success",
          "Password changed",
          "Every other session has been signed out.",
        );
      } catch (error) {
        const unplaced = isApiError(error) ? helpers.applyServerErrors(error) : [];
        setPasswordError(unplaced[0] ?? messageOf(error));
      }
    },
  });

  const signOutEverywhere = useAction(() => authApi.logoutEverywhere(), {
    onSuccess: () => {
      // This session was revoked too, so there is nothing left to stay on.
      void signOut();
    },
  });

  return (
    <div className="space-y-5 pb-8">
      <FormSheet
        title={user.full_name ?? user.login_id}
        subtitle={user.login_id}
        status={
          <Badge
            className={
              isManager
                ? "bg-brand-100 text-brand-700 ring-brand-200"
                : "bg-slate-100 text-slate-700 ring-slate-300"
            }
            title={
              isManager
                ? "Can manage products, warehouses and locations"
                : "Can run operations, but not change master data"
            }
          >
            {isManager ? "Manager" : "Warehouse staff"}
          </Badge>
        }
      >
        <form onSubmit={profileForm.handleSubmit} noValidate>
          {profileError && (
            <div className="mt-4">
              <FormAlert message={profileError} />
            </div>
          )}

          <FormSection title="Details">
            <Field label="Full name" error={profileForm.errorFor("full_name")}>
              {(aria) => <Input {...aria} {...profileForm.field("full_name")} autoComplete="name" />}
            </Field>

            <Field label="Email" error={profileForm.errorFor("email")} required>
              {(aria) => (
                <Input {...aria} {...profileForm.field("email")} type="email" autoComplete="email" />
              )}
            </Field>

            <ReadField label="Login ID">{user.login_id}</ReadField>
            <ReadField label="Member since">{formatDate(user.created_at)}</ReadField>
          </FormSection>

          <div className="mt-5 flex justify-end">
            <Button type="submit" variant="primary" loading={profileForm.submitting}>
              Save changes
            </Button>
          </div>
        </form>
      </FormSheet>

      <div className="mx-auto max-w-5xl px-4">
        <div className="sheet p-5 sm:p-7">
          <h2 className="border-b border-line pb-3 text-base font-semibold text-brand-700">
            Change password
          </h2>

          <form onSubmit={passwordForm.handleSubmit} noValidate>
            {passwordError && (
              <div className="mt-4">
                <FormAlert message={passwordError} />
              </div>
            )}

            <div className="mt-4 grid gap-x-8 gap-y-4 sm:grid-cols-2">
              <Field
                label="Current password"
                error={passwordForm.errorFor("current_password")}
                required
              >
                {(aria) => (
                  <Input
                    {...aria}
                    {...passwordForm.field("current_password")}
                    type="password"
                    autoComplete="current-password"
                  />
                )}
              </Field>

              <div className="hidden sm:block" />

              <Field label="New password" error={passwordForm.errorFor("password")} required>
                {(aria) => (
                  <Input
                    {...aria}
                    {...passwordForm.field("password")}
                    type="password"
                    autoComplete="new-password"
                  />
                )}
              </Field>

              <Field
                label="Confirm new password"
                error={passwordForm.errorFor("confirm_password")}
                required
              >
                {(aria) => (
                  <Input
                    {...aria}
                    {...passwordForm.field("confirm_password")}
                    type="password"
                    autoComplete="new-password"
                  />
                )}
              </Field>
            </div>

            <div className="mt-4">
              <PasswordRules value={String(passwordForm.values.password ?? "")} />
            </div>

            <div className="mt-5 flex items-center justify-between gap-3">
              <p className="text-xs text-ink-muted">
                Changing your password signs out every other device.
              </p>
              <Button type="submit" variant="primary" loading={passwordForm.submitting}>
                Change password
              </Button>
            </div>
          </form>
        </div>
      </div>

      <div className="mx-auto max-w-5xl px-4">
        <div className="sheet flex flex-wrap items-center justify-between gap-3 p-5">
          <div>
            <h2 className="text-base font-semibold text-brand-700">Sessions</h2>
            <p className="mt-0.5 text-sm text-ink-muted">
              Signing out everywhere revokes every refresh token for this account,
              including the one in this browser.
            </p>
          </div>
          <Button variant="danger" onClick={() => setConfirmingSignOutAll(true)}>
            Sign out everywhere
          </Button>
        </div>
      </div>

      <ConfirmDialog
        open={confirmingSignOutAll}
        title="Sign out of every device?"
        message="You will need to sign in again here as well."
        confirmLabel="Sign out everywhere"
        destructive
        pending={signOutEverywhere.pending}
        onConfirm={() => void signOutEverywhere.run()}
        onClose={() => setConfirmingSignOutAll(false)}
      />
    </div>
  );
}
