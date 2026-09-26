import { describe, it, expect } from "vitest";
import {
  toNumber,
  formatQuantity,
  formatMoney,
  formatDate,
  formatDateTime,
  todayIso,
  productLabel,
  userLabel,
  initials,
  pluralise,
} from "@/lib/format";

describe("toNumber", () => {
  it("converts a string decimal to a number", () => {
    expect(toNumber("42.5")).toBe(42.5);
  });

  it("returns 0 for null", () => {
    expect(toNumber(null)).toBe(0);
  });

  it("returns 0 for undefined", () => {
    expect(toNumber(undefined)).toBe(0);
  });

  it("passes through a numeric value", () => {
    expect(toNumber(7)).toBe(7);
  });

  it("returns 0 for NaN-producing strings", () => {
    expect(toNumber("not-a-number")).toBe(0);
  });
});

describe("formatQuantity", () => {
  it("formats a whole number without trailing zeros", () => {
    const result = formatQuantity("50.000");
    expect(result).toMatch(/50/);
  });

  it("preserves meaningful decimals", () => {
    const result = formatQuantity("0.5");
    expect(result).toMatch(/0\.5/);
  });

  it("handles null", () => {
    expect(formatQuantity(null)).toMatch(/0/);
  });
});

describe("formatMoney", () => {
  it("prefixes with the rupee symbol", () => {
    expect(formatMoney(1000)).toMatch(/₹/);
  });

  it("shows two decimal places", () => {
    expect(formatMoney(42)).toMatch(/42\.00/);
  });
});

describe("formatDate", () => {
  it("returns a dash for null", () => {
    expect(formatDate(null)).toBe("—");
  });

  it("returns a dash for undefined", () => {
    expect(formatDate(undefined)).toBe("—");
  });

  it("formats a valid ISO date string", () => {
    const result = formatDate("2025-03-15T00:00:00Z");
    // Should contain the year at minimum
    expect(result).toMatch(/2025/);
  });

  it("returns a dash for garbage input", () => {
    expect(formatDate("not-a-date")).toBe("—");
  });
});

describe("formatDateTime", () => {
  it("returns a dash for null", () => {
    expect(formatDateTime(null)).toBe("—");
  });

  it("includes the year for a valid date", () => {
    const result = formatDateTime("2025-06-01T14:30:00Z");
    expect(result).toMatch(/2025/);
  });
});

describe("todayIso", () => {
  it("returns a YYYY-MM-DD string", () => {
    expect(todayIso()).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });
});

describe("productLabel", () => {
  it("formats [SKU] Name", () => {
    expect(productLabel({ sku: "WDG-001", name: "Widget" })).toBe("[WDG-001] Widget");
  });
});

describe("userLabel", () => {
  it("uses full_name when available", () => {
    expect(userLabel({ full_name: "Jane Doe", login_id: "jane" })).toBe("Jane Doe");
  });

  it("falls back to login_id when full_name is null", () => {
    expect(userLabel({ full_name: null, login_id: "jane" })).toBe("jane");
  });

  it("falls back to login_id when full_name is whitespace", () => {
    expect(userLabel({ full_name: "   ", login_id: "jane" })).toBe("jane");
  });
});

describe("initials", () => {
  it("returns two-letter initials for a two-word name", () => {
    expect(initials("Jane Doe")).toBe("JD");
  });

  it("returns one letter for a single-word name", () => {
    expect(initials("Admin")).toBe("A");
  });

  it("returns ? for an empty string", () => {
    expect(initials("")).toBe("?");
  });

  it("handles extra whitespace", () => {
    expect(initials("  John   Smith  ")).toBe("JS");
  });
});

describe("pluralise", () => {
  it("uses singular for count 1", () => {
    expect(pluralise(1, "item")).toBe("1 item");
  });

  it("uses plural for count 0", () => {
    expect(pluralise(0, "item")).toBe("0 items");
  });

  it("uses plural for count > 1", () => {
    expect(pluralise(5, "item")).toBe("5 items");
  });

  it("accepts a custom plural form", () => {
    expect(pluralise(3, "category", "categories")).toBe("3 categories");
  });
});
