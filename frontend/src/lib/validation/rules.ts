import { z } from "zod";

/**
 * Field rules mirroring `backend/app/schemas/fields.py`.
 *
 * The server is still the authority: everything here is checked again in Pydantic, in
 * the services, and by database constraints. Validating in the browser only means the
 * user finds out about a typo before a round trip, and the rules are kept in this one
 * file so the two sides cannot drift apart unnoticed.
 */

export const LOGIN_ID_PATTERN = /^[A-Za-z0-9_.]+$/;
export const SKU_PATTERN = /^[A-Za-z0-9][A-Za-z0-9-]{1,31}$/;
export const WAREHOUSE_CODE_PATTERN = /^[A-Za-z0-9]{1,5}$/;
export const LOCATION_CODE_PATTERN = /^[A-Za-z0-9-]{1,20}$/;

/** bcrypt only reads the first 72 bytes, so anything longer would silently truncate. */
export const PASSWORD_MIN_LENGTH = 9;
export const PASSWORD_MAX_LENGTH = 72;

export const loginId = z
  .string()
  .trim()
  .min(6, "Login ID must be at least 6 characters")
  .max(12, "Login ID must be at most 12 characters")
  .regex(LOGIN_ID_PATTERN, "Use letters, numbers, dots and underscores only");

export const email = z
  .string()
  .trim()
  .min(1, "Email is required")
  .email("Enter a valid email address");

/** The rule printed on the sign-up mockup, matching `validate_password_strength`. */
export const password = z
  .string()
  .min(PASSWORD_MIN_LENGTH, `Password must be at least ${PASSWORD_MIN_LENGTH} characters`)
  .max(PASSWORD_MAX_LENGTH, `Password must be at most ${PASSWORD_MAX_LENGTH} characters`)
  .regex(/[a-z]/, "Password must contain a lowercase letter")
  .regex(/[A-Z]/, "Password must contain an uppercase letter")
  .regex(/[^A-Za-z0-9]/, "Password must contain a special character");

export const otpCode = z
  .string()
  .trim()
  .regex(/^\d{6}$/, "Enter the 6-digit code");

export const sku = z
  .string()
  .trim()
  .toUpperCase()
  .min(2, "SKU must be at least 2 characters")
  .max(32, "SKU must be at most 32 characters")
  .regex(SKU_PATTERN, "Start with a letter or number; letters, numbers and hyphens only");

export const warehouseCode = z
  .string()
  .trim()
  .toUpperCase()
  .min(1, "Short code is required")
  .max(5, "Short code must be at most 5 characters")
  .regex(WAREHOUSE_CODE_PATTERN, "Letters and numbers only");

export const locationCode = z
  .string()
  .trim()
  .min(1, "Short code is required")
  .max(20, "Short code must be at most 20 characters")
  .regex(LOCATION_CODE_PATTERN, "Letters, numbers and hyphens only");

/** Required text of a bounded length, used for names and labels. */
export function boundedText(max: number, label: string) {
  return z.string().trim().min(1, `${label} is required`).max(max, `${label} is too long`);
}

/** Optional text: an empty box means "not given", not an empty string. */
export function optionalText(max: number, label: string) {
  return z
    .string()
    .trim()
    .max(max, `${label} is too long`)
    .transform((value) => (value === "" ? null : value))
    .nullable();
}

interface DecimalOptions {
  label: string;
  /** Digits after the point, matching the column's scale. */
  scale: number;
  /** Reject zero as well as negatives. Quantities to move must be positive. */
  positive?: boolean;
}

/**
 * A decimal kept as a string all the way to the API.
 *
 * Quantities are `NUMERIC` in PostgreSQL and arrive as JSON strings, so parsing them
 * into a float here would introduce exactly the rounding the database was chosen to
 * avoid. The value is validated, normalised and passed on as text.
 */
export function decimalString({ label, scale, positive = false }: DecimalOptions) {
  return z
    .string()
    .trim()
    .min(1, `${label} is required`)
    .superRefine((value, ctx) => {
      if (!/^\d+(\.\d+)?$/.test(value)) {
        ctx.addIssue({ code: z.ZodIssueCode.custom, message: `${label} must be a number` });
        return;
      }
      const [, fraction = ""] = value.split(".");
      if (fraction.length > scale) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: `${label} allows at most ${scale} decimal place${scale === 1 ? "" : "s"}`,
        });
      }
      if (positive && Number(value) <= 0) {
        ctx.addIssue({ code: z.ZodIssueCode.custom, message: `${label} must be greater than 0` });
      }
    });
}

/** Quantities: `NUMERIC(14, 3)`. */
export const quantity = decimalString({ label: "Quantity", scale: 3, positive: true });
export const countedQuantity = decimalString({ label: "Counted quantity", scale: 3 });
/** Money: `NUMERIC(12, 2)`. */
export const unitCost = decimalString({ label: "Unit cost", scale: 2 });

/**
 * A `<select>` value.
 *
 * The DOM always hands back a string, so that is what the form holds; the API wants a
 * positive integer, so that is what the schema produces. Keeping the conversion here
 * means no form has to remember to do it, and "" becomes a required-field message
 * rather than a `NaN` in the request body.
 */
export function selectId(label: string) {
  return z
    .string()
    .min(1, `${label} is required`)
    .transform(Number)
    .pipe(z.number().int().positive(`${label} is required`));
}

/** The same field optional, where an empty `<select>` means "none". */
export function optionalSelectId() {
  return z
    .string()
    .transform((value) => (value.trim() === "" ? null : Number(value)))
    .pipe(z.number().int().positive("Choose a valid option").nullable());
}

/** An ISO date (`YYYY-MM-DD`) as produced by `<input type="date">`. */
export const isoDate = z
  .string()
  .regex(/^\d{4}-\d{2}-\d{2}$/, "Enter a valid date");
