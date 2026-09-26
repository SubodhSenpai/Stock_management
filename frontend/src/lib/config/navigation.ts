import type { UserRole } from "@/types/api";

/**
 * The top navigation, as data.
 *
 * Mirrors the mockup: Dashboard · Operations · Products · Move History · Settings.
 * `managerOnly` hides what the signed-in user could not do anyway; the server still
 * enforces it, so hiding is a courtesy rather than the control.
 */

export interface NavLink {
  label: string;
  href: string;
  description?: string;
  managerOnly?: boolean;
}

export interface NavItem {
  label: string;
  href?: string;
  children?: NavLink[];
}

export const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", href: "/dashboard" },
  {
    label: "Operations",
    children: [
      { label: "Receipts", href: "/operations/receipts", description: "Goods arriving" },
      { label: "Delivery Orders", href: "/operations/deliveries", description: "Goods shipping out" },
      { label: "Internal Transfers", href: "/operations/transfers", description: "Between locations" },
      { label: "Adjustments", href: "/operations/adjustments", description: "After a physical count" },
    ],
  },
  {
    label: "Products",
    children: [
      { label: "Products", href: "/products", description: "Catalogue and stock" },
      { label: "Stock", href: "/stock", description: "On hand and free to use" },
      { label: "Categories", href: "/products/categories" },
      { label: "Reordering Rules", href: "/products/reorder-rules" },
    ],
  },
  { label: "Move History", href: "/moves" },
  {
    label: "Settings",
    children: [
      { label: "Warehouses", href: "/settings/warehouses", managerOnly: true },
      { label: "Locations", href: "/settings/locations", managerOnly: true },
      { label: "Contacts", href: "/settings/contacts", description: "Vendors and customers" },
    ],
  },
];

/** Drop the entries this role cannot use, so no dead links are shown. */
export function navigationFor(role: UserRole): NavItem[] {
  if (role === "manager") return NAV_ITEMS;
  return NAV_ITEMS.map((item) =>
    item.children
      ? { ...item, children: item.children.filter((child) => !child.managerOnly) }
      : item,
  ).filter((item) => !item.children || item.children.length > 0);
}
