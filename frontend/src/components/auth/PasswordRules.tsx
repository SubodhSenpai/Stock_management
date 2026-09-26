"use client";

import { cn } from "@/lib/cn";
import { PASSWORD_MIN_LENGTH } from "@/lib/validation/rules";

/**
 * The password rules, ticked off as they are met.
 *
 * Shows the same four conditions the backend checks, so the user can see why a
 * password is being refused before pressing the button rather than after.
 */
const RULES: Array<{ label: string; met: (value: string) => boolean }> = [
  { label: `At least ${PASSWORD_MIN_LENGTH} characters`, met: (v) => v.length >= PASSWORD_MIN_LENGTH },
  { label: "A lowercase letter", met: (v) => /[a-z]/.test(v) },
  { label: "An uppercase letter", met: (v) => /[A-Z]/.test(v) },
  { label: "A special character", met: (v) => /[^A-Za-z0-9]/.test(v) },
];

export function PasswordRules({ value }: { value: string }) {
  if (value === "") return null;

  return (
    <ul className="grid gap-1 rounded border border-line bg-canvas px-3 py-2 sm:grid-cols-2">
      {RULES.map((rule) => {
        const met = rule.met(value);
        return (
          <li
            key={rule.label}
            className={cn(
              "flex items-center gap-1.5 text-xs",
              met ? "text-emerald-700" : "text-ink-muted",
            )}
          >
            <span aria-hidden>{met ? "✓" : "○"}</span>
            {rule.label}
            <span className="sr-only">{met ? " (met)" : " (not yet met)"}</span>
          </li>
        );
      })}
    </ul>
  );
}
