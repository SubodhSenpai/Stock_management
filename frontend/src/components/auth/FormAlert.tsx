import { cn } from "@/lib/cn";

/**
 * A message that belongs to the whole form rather than one field: "Invalid login ID or
 * password", "Too many attempts", or the confirmation that a reset code was sent.
 */
export function FormAlert({
  message,
  variant = "error",
}: {
  message?: string;
  variant?: "error" | "success" | "info";
}) {
  if (!message) return null;

  return (
    <p
      role="alert"
      className={cn(
        "rounded border px-3 py-2 text-sm",
        variant === "error" && "border-rose-200 bg-rose-50 text-rose-700",
        variant === "success" && "border-emerald-200 bg-emerald-50 text-emerald-800",
        variant === "info" && "border-sky-200 bg-sky-50 text-sky-800",
      )}
    >
      {message}
    </p>
  );
}
