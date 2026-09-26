import { describe, it, expect } from "vitest";
import { cn } from "@/lib/cn";

describe("cn (class name utility)", () => {
  it("joins multiple class strings", () => {
    expect(cn("foo", "bar", "baz")).toBe("foo bar baz");
  });

  it("filters out false values", () => {
    expect(cn("always", false && "never", "present")).toBe("always present");
  });

  it("filters out null and undefined", () => {
    expect(cn("a", null, undefined, "b")).toBe("a b");
  });

  it("returns empty string when all values are falsy", () => {
    expect(cn(false, null, undefined)).toBe("");
  });

  it("returns empty string with no arguments", () => {
    expect(cn()).toBe("");
  });
});
