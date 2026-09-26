/**
 * Join class names, skipping anything falsy.
 *
 * Small enough not to justify a dependency: components use it to add conditional
 * classes without string concatenation in the JSX.
 */
export type ClassValue = string | false | null | undefined;

export function cn(...classes: ClassValue[]): string {
  return classes.filter(Boolean).join(" ");
}
