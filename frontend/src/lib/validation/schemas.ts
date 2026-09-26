import { z } from "zod";
import {
  boundedText,
  countedQuantity,
  email,
  isoDate,
  locationCode,
  loginId,
  optionalSelectId,
  optionalText,
  otpCode,
  password,
  quantity,
  selectId,
  sku,
  unitCost,
  warehouseCode,
} from "./rules";

/**
 * Form schemas, one per screen that accepts input.
 *
 * Each schema is the single description of what a form accepts: the inputs read their
 * constraints from it, `useForm` runs it on submit, and the inferred type is what the
 * submit handler receives. Adding a field in one place and forgetting it in another
 * becomes a type error rather than a runtime surprise.
 */

// ------------------------------------------------------------------ sessions

export const loginSchema = z.object({
  // Deliberately loose, matching the backend: a malformed login id must fail
  // authentication rather than validation, or the error reveals which field was wrong.
  login_id: z.string().trim().min(1, "Login ID is required").max(64),
  password: z.string().min(1, "Password is required").max(128),
});

export const signupSchema = z
  .object({
    login_id: loginId,
    email,
    full_name: optionalText(100, "Name"),
    password,
    confirm_password: z.string().min(1, "Confirm your password"),
  })
  .refine((values) => values.password === values.confirm_password, {
    path: ["confirm_password"],
    message: "Passwords do not match",
  });

export const forgotPasswordSchema = z.object({ email });

export const verifyOtpSchema = z.object({ otp: otpCode });

export const resetPasswordSchema = z
  .object({
    password,
    confirm_password: z.string().min(1, "Confirm your password"),
  })
  .refine((values) => values.password === values.confirm_password, {
    path: ["confirm_password"],
    message: "Passwords do not match",
  });

export const changePasswordSchema = z
  .object({
    current_password: z.string().min(1, "Enter your current password").max(128),
    password,
    confirm_password: z.string().min(1, "Confirm your password"),
  })
  .refine((values) => values.password === values.confirm_password, {
    path: ["confirm_password"],
    message: "Passwords do not match",
  });

export const profileSchema = z.object({
  full_name: optionalText(100, "Name"),
  email,
});

// ------------------------------------------------------------------ catalog

export const productSchema = z.object({
  sku,
  name: boundedText(150, "Name"),
  category_id: selectId("Category"),
  uom_id: selectId("Unit of measure"),
  unit_cost: unitCost,
  initial_location_id: optionalSelectId(),
  initial_quantity: z.string().trim(),
});

/**
 * Editing a product.
 *
 * `sku` is carried so the shared field set can show it, but it is read-only and never
 * submitted: past documents already cite it, so changing it would rewrite history.
 */
export const productEditSchema = z.object({
  sku: z.string(),
  name: boundedText(150, "Name"),
  category_id: selectId("Category"),
  uom_id: selectId("Unit of measure"),
  unit_cost: unitCost,
});

export const categorySchema = z.object({ name: boundedText(80, "Name") });

export const reorderRuleSchema = z
  .object({
    product_id: selectId("Product"),
    warehouse_id: selectId("Warehouse"),
    min_quantity: countedQuantity,
    max_quantity: countedQuantity,
  })
  .refine((values) => Number(values.max_quantity) >= Number(values.min_quantity), {
    path: ["max_quantity"],
    message: "Maximum must be at least the minimum",
  });

// ------------------------------------------------------------------ places

export const warehouseSchema = z.object({
  name: boundedText(100, "Name"),
  short_code: warehouseCode,
  address: optionalText(500, "Address"),
});

export const warehouseEditSchema = z.object({
  name: boundedText(100, "Name"),
  address: optionalText(500, "Address"),
});

export const locationSchema = z.object({
  name: boundedText(100, "Name"),
  short_code: locationCode,
  warehouse_id: selectId("Warehouse"),
});

export const partnerSchema = z.object({
  name: boundedText(120, "Name"),
  type: z.enum(["vendor", "customer", "both"]),
  email: z.union([z.literal(""), email]).transform((value) => (value === "" ? null : value)),
  phone: optionalText(20, "Phone"),
  address: optionalText(500, "Address"),
});

// ------------------------------------------------------------------ documents

/**
 * One row of the lines editor.
 *
 * `product_id` is 0 on a row the user has not filled in yet, which the positive check
 * turns into "Choose a product" against that row rather than a message about the whole
 * document. Adjustments record a counted quantity, which may legitimately be zero;
 * everything else moves a quantity, which may not.
 */
function operationLineSchema(counted: boolean) {
  return z.object({
    product_id: z.number().int().positive("Choose a product"),
    quantity: counted ? countedQuantity : quantity,
  });
}

/** The document header, shared by all four types. */
function operationBaseSchema(counted: boolean) {
  return z.object({
    partner_id: optionalSelectId(),
    source_location_id: optionalSelectId(),
    dest_location_id: optionalSelectId(),
    delivery_address: optionalText(500, "Delivery address"),
    schedule_date: isoDate,
    notes: optionalText(2000, "Notes"),
    lines: z
      .array(operationLineSchema(counted))
      .min(1, "Add at least one product")
      .max(200, "A document may hold at most 200 lines")
      .superRefine((lines, ctx) => {
        const seen = new Set<number>();
        lines.forEach((line, index) => {
          if (line.product_id && seen.has(line.product_id)) {
            ctx.addIssue({
              code: z.ZodIssueCode.custom,
              path: [index, "product_id"],
              message: "This product is already on the document; combine the quantities",
            });
          }
          seen.add(line.product_id);
        });
      }),
  });
}

export type OperationFormValues = z.input<ReturnType<typeof operationBaseSchema>>;

/**
 * The document schema for one type.
 *
 * A receipt needs somewhere to put the goods, a delivery needs somewhere to take them
 * from, a transfer needs both, and an adjustment needs the location being counted.
 */
export function operationSchemaFor(type: "receipt" | "delivery" | "internal" | "adjustment") {
  return operationBaseSchema(type === "adjustment").superRefine((values, ctx) => {
    const require = (field: "source_location_id" | "dest_location_id", message: string) => {
      if (!values[field]) {
        ctx.addIssue({ code: z.ZodIssueCode.custom, path: [field], message });
      }
    };
    if (type === "receipt") require("dest_location_id", "Choose where the goods arrive");
    if (type === "delivery") require("source_location_id", "Choose where the goods ship from");
    if (type === "adjustment") require("source_location_id", "Choose the location being counted");
    if (type === "internal") {
      require("source_location_id", "Choose the source location");
      require("dest_location_id", "Choose the destination location");
      if (
        values.source_location_id &&
        values.source_location_id === values.dest_location_id
      ) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["dest_location_id"],
          message: "Source and destination must be different",
        });
      }
    }
  });
}

export const stockAdjustSchema = z.object({
  counted_quantity: countedQuantity,
});
